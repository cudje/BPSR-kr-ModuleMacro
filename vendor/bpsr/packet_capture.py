"""
网络抓包模块
"""

import io
import socket
import struct
import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from scapy.all import sniff, IP, TCP, UDP, Raw
import zstandard as zstd
import json
from BlueProtobuf_pb2 import SyncContainerData, CharSerialize, ItemPackage, Package, Item, ModNewAttr
from logging_config import get_logger
from module_parser import ModuleParser

logger = get_logger(__name__)


class BinaryReader:
    """二进制数据读取器"""
    
    def __init__(self, buffer: bytes, offset: int = 0):
        self.buffer = buffer
        self.offset = offset
        
    def readUInt64(self) -> int:
        """读取64位无符号整数(大端序)"""
        value = struct.unpack('>Q', self.buffer[self.offset:self.offset + 8])[0]
        self.offset += 8
        return value
        
    def readUInt32(self) -> int:
        """读取32位无符号整数(大端序)"""
        value = struct.unpack('>I', self.buffer[self.offset:self.offset + 4])[0]
        self.offset += 4
        return value
        
    def peekUInt32(self) -> int:
        """查看32位无符号整数(大端序)，不推进偏移量"""
        return struct.unpack('>I', self.buffer[self.offset:self.offset + 4])[0]
        
    def readUInt16(self) -> int:
        """读取16位无符号整数(大端序)"""
        value = struct.unpack('>H', self.buffer[self.offset:self.offset + 2])[0]
        self.offset += 2
        return value
        
    def readBytes(self, length: int) -> bytes:
        """读取指定长度的字节"""
        value = self.buffer[self.offset:self.offset + length]
        self.offset += length
        return value
        
    def remaining(self) -> int:
        """返回剩余字节数"""
        return len(self.buffer) - self.offset
        
    def readRemaining(self) -> bytes:
        """读取剩余的所有字节"""
        value = self.buffer[self.offset:]
        self.offset = len(self.buffer)
        return value


class PacketCapture:
    """网络数据包抓取器"""
    
    def __init__(self, interface: str = None):
        """
        初始化抓包器
        
        Args:
            interface: 网络接口名称, None表示自动选择
        """
        self.interface = interface
        self.is_running = False
        self.callback = None
        self.packet_count = 0
        self.sync_container_count = 0
        
        self.current_server = ''
        self.tcp_cache = {}
        self.tcp_next_seq = -1
        self.tcp_last_time = 0
        self.tcp_lock = threading.Lock()
        self._data = b''

        self.module_parser = ModuleParser()
        # 게임 서버로 확정되기 전 조각. 확정 패킷을 버리지 않고 이어서 해석한다.
        self._pending = {}
        self._feeds = {}
        self._threads = []
        self._module_seen = False
        self._zstd = None
        self._cache_limit = 2 * 1024 * 1024
        
    def start_capture(self, callback: Callable[[Dict[str, Any]], None] = None):
        """
        开始抓包
        
        Args:
            callback: 数据包处理回调函数
        """
        self.callback = self._remember_module
        self._user_callback = callback
        self.is_running = True
        self._module_seen = False
        
        logger.debug("패킷 캡처 시작: %s", self.interface or "자동")
        
        # 在新线程中运行抓包
        capture_thread = threading.Thread(target=self._capture_loop, name="module-packet")
        capture_thread.daemon = True
        capture_thread.start()
        
        # 启动定时清理线程
        cleanup_thread = threading.Thread(target=self._cleanup_loop, name="module-packet-cleanup")
        cleanup_thread.daemon = True
        cleanup_thread.start()
        self._threads = [capture_thread, cleanup_thread]
        
    def stop_capture(self):
        """停止抓包"""
        self.is_running = False
        for thread in list(self._threads):
            if thread is not threading.current_thread():
                thread.join(timeout=2.0)
        self._threads.clear()
        with self.tcp_lock:
            self._pending.clear()
            self._feeds.clear()
            self.tcp_cache.clear()
            self._data = b""
        logger.debug("패킷 캡처 중지")
        
    def _remember_module(self, data) -> None:
        if isinstance(data, dict) and data.get("v_data") is not None:
            self._module_seen = True
        if self._user_callback is not None:
            self._user_callback(data)

    def _install_capture_buffer(self) -> None:
        """Npcap 커널 통을 키운다. conf.bufsize 는 Windows에서 적용되지 않는다."""
        try:
            from scapy.libs import winpcapy
        except ImportError:
            return
        if getattr(winpcapy, "_modulemacro_buffer", False):
            return
        activate = getattr(winpcapy, "pcap_activate", None)
        set_buffer = getattr(winpcapy, "pcap_set_buffer_size", None)
        if activate is None or set_buffer is None:
            return
        size = 32 * 1024 * 1024

        def _activate(pcap):
            set_buffer(pcap, size)
            return activate(pcap)

        winpcapy.pcap_activate = _activate
        winpcapy._modulemacro_buffer = True

    def _prefer_capture(self) -> None:
        """게임 창이 앞에 있어도 패킷 읽기가 밀리지 않게 우선순위를 올린다."""
        try:
            kernel32 = __import__("ctypes").windll.kernel32
            # ABOVE_NORMAL. 전체 화면 게임이 앞에 있으면 기본 우선순위로는 버퍼가 넘친다.
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00008000)
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), 2)
        except Exception:
            logger.debug("캡처 우선순위 변경 실패", exc_info=True)

    def _capture_loop(self):
        """抓包主循环"""
        self._prefer_capture()
        self._install_capture_buffer()
        try:
            # timeout으로 끊어 읽어야 stop_capture 이후 스레드가 패킷을 기다린 채 남지 않는다.
            while self.is_running:
                sniff(
                    iface=self.interface,
                    filter="tcp",
                    prn=self._process_packet,
                    store=0,
                    timeout=1,
                    stop_filter=lambda _: not self.is_running,
                )
        except Exception as e:
            logger.error(f"抓包过程中发生错误: {e}")
            
    def _process_packet(self, packet):
        """处理单个数据包"""
        if not self.is_running or self._module_seen:
            return
            
        self.packet_count += 1
        
        try:
            # 检查是否是TCP包
            if TCP in packet and IP in packet:
                self._process_tcp_packet(packet)
        except Exception as e:
            logger.debug(f"处理数据包时发生错误: {e}")
            
    def _process_tcp_packet(self, packet):
        """处理TCP数据包"""
        # 获取IP和TCP信息
        ip_layer = packet[IP]
        tcp_layer = packet[TCP]
        
        src_addr = ip_layer.src
        dst_addr = ip_layer.dst
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport
        seq = tcp_layer.seq
        ack = tcp_layer.ack
        
        # 构建服务器标识
        src_server = f"{src_addr}:{src_port} -> {dst_addr}:{dst_port}"
        
        # 获取TCP负载
        if Raw in packet:
            payload = bytes(packet[Raw])
            self._process_tcp_stream(src_server, seq, payload)
            
    def _seq_on_or_after(self, seq: int, start: int) -> bool:
        """TCP 순서번호 start 이후인지. 앞쪽 절반만 뒤로 본다."""
        return ((seq - start) & 0xFFFFFFFF) < 0x80000000

    def _trim_pending(self, pending: dict) -> None:
        if len(pending) <= 80:
            return
        for old in sorted(pending)[:-80]:
            del pending[old]

    def _contiguous_from_oldest(self, pending: dict) -> tuple[bytes, int]:
        seqs = sorted(pending)
        if not seqs:
            return b"", 0
        start = seqs[0]
        expect = start
        blob = bytearray()
        for seq in seqs:
            if seq != expect:
                break
            chunk = pending[seq]
            blob += chunk
            expect = (seq + len(chunk)) & 0xFFFFFFFF
        return bytes(blob), start

    def _pending_game_start(self, pending: dict) -> int | None:
        """서명으로 게임 서버가 확인되는 첫 순서번호. 없으면 None."""
        for seq in sorted(pending):
            if self._identify_game_server(pending[seq]):
                return seq
        blob, start = self._contiguous_from_oldest(pending)
        if blob and self._identify_game_server(blob):
            return start
        return None

    def _contiguous_from(self, pending: dict, start: int) -> tuple[bytes, int]:
        """start부터 끊기지 않은 조각을 붙이고, 다음 순서번호를 돌려준다."""
        blob = bytearray()
        expect = start
        for seq in sorted(pending):
            if not self._seq_on_or_after(seq, start):
                continue
            if seq != expect:
                break
            chunk = pending[seq]
            blob += chunk
            expect = (seq + len(chunk)) & 0xFFFFFFFF
        return bytes(blob), expect

    def _decompress(self, payload: bytes) -> bytes:
        if self._zstd is None:
            self._zstd = zstd.ZstdDecompressor()
        return self._zstd.decompress(payload, max_output_size=1024 * 1024)

    def _trim_bytes(self, pending: dict, limit: int | None = None) -> None:
        """오래된 조각부터 버려 한 흐름이 limit 바이트를 넘지 않게 한다."""
        cap = self._cache_limit if limit is None else limit
        total = sum(len(buf) for buf in pending.values())
        if total <= cap:
            return
        owner = id(pending)
        for old in sorted(pending):
            total -= len(pending.pop(old))
            self._feeds.pop((owner, old), None)
            if total <= cap:
                break

    def _cap_flows(self, current: str) -> None:
        while len(self._pending) > 24:
            victim = None
            for key, packets in self._pending.items():
                if key == current:
                    continue
                if victim is None or len(packets) < len(self._pending[victim]):
                    victim = key
            if victim is None:
                break
            owner = id(self._pending[victim])
            del self._pending[victim]
            for key in [key for key in self._feeds if key[0] == owner]:
                del self._feeds[key]

    def _island_start(self, pending: dict, seq: int) -> int | None:
        start = None
        expect = None
        for item_seq in sorted(pending):
            if expect is None or item_seq != expect:
                start = item_seq
            if item_seq == seq:
                return start
            expect = (item_seq + len(pending[item_seq])) & 0xFFFFFFFF
        return None

    def _consume(self, blob: bytes) -> bytes:
        """새 바이트만 메시지 해석하고, 아직 메시지가 안 끝난 꼬리를 돌려준다."""
        if self._module_seen or not blob:
            return b""
        saved = self._data
        self._data = blob
        try:
            self._process_complete_packets()
            return self._data
        finally:
            self._data = saved

    def _feed_segment(self, pending: dict, seq: int) -> None:
        """방금 들어온 조각이 속한 연속 구간만 이어서 해석한다."""
        if self._module_seen or seq not in pending:
            return
        start = self._island_start(pending, seq)
        if start is None:
            return
        payload = pending[seq]
        end = (seq + len(payload)) & 0xFFFFFFFF
        key = (id(pending), start)
        state = self._feeds.get(key)
        if state is not None and state["expect"] == seq:
            state["tail"] = self._consume(state["tail"] + payload)
            state["expect"] = end
            state["end"] = end
            return
        blob, end_seq = self._contiguous_from(pending, start)
        if state is not None and state.get("end") == end_seq:
            return
        self._feeds[key] = {
            "expect": end_seq,
            "tail": self._consume(blob),
            "end": end_seq,
        }

    def _process_tcp_stream(self, src_server: str, seq: int, payload: bytes):
        """处理TCP流数据"""
        with self.tcp_lock:
            if self._module_seen:
                return
            # 서버를 알기 전에는 조각을 모아 둔다.
            # 확인된 묶음은 따로 해석하고, 그 다음 순서부터 기존 재조립을 이어간다.
            if self.current_server != src_server:
                pending = self._pending.setdefault(src_server, {})
                pending[seq] = payload
                self._trim_pending(pending)
                self._trim_bytes(pending, 512 * 1024)
                self._cap_flows(src_server)
                self._feed_segment(pending, seq)
                start = self._pending_game_start(pending)
                if start is None:
                    return
                blob, end_seq = self._contiguous_from(pending, start)
                rest = {
                    item_seq: item
                    for item_seq, item in pending.items()
                    if self._seq_on_or_after(item_seq, end_seq)
                }
                self._pending.clear()
                self._feeds.clear()
                self.current_server = src_server
                self._consume(blob)
                self._clear_tcp_cache()
                self.tcp_next_seq = end_seq
                self.tcp_cache.update(rest)
                logger.debug("게임 서버 확인: %s", src_server)
                return

            if not self.current_server:
                return
                
            # TCP流重组逻辑
            if self.tcp_next_seq == -1:
                logger.error('TCP流重组错误: tcp_next_seq 为 -1')
                if len(payload) > 4 and struct.unpack('>I', payload[:4])[0] < 0x0fffff:
                    self.tcp_next_seq = seq
                return
                
            # 缓存数据包
            incoming = seq
            if (self.tcp_next_seq - seq) <= 0 or self.tcp_next_seq == -1:
                self.tcp_cache[seq] = payload
                self._trim_bytes(self.tcp_cache)
                
            # 按顺序处理数据包
            while self.tcp_next_seq in self.tcp_cache:
                seq = self.tcp_next_seq
                cached_data = self.tcp_cache[seq]
                self._data = self._data + cached_data if self._data else cached_data
                self.tcp_next_seq = (seq + len(cached_data)) & 0xffffffff
                del self.tcp_cache[seq]
                self.tcp_last_time = time.time()
                
            # 处理完整的数据包
            self._process_complete_packets()
            # 앞에 빠진 조각이 있어도, 그 뒤의 연속 구간은 따로 해석한다.
            if incoming in self.tcp_cache:
                self._feed_segment(self.tcp_cache, incoming)
            
    def _identify_game_server(self, payload: bytes) -> bool:
        """识别游戏服务器"""
        if len(payload) < 10:
            return False
            
        try:
            if payload[4] == 0:
                data = payload[10:]
                if data:
                    # 检查游戏服务器签名
                    signature = b'\x00\x63\x33\x53\x42\x00'
                    stream = io.BytesIO(data)
                    while True:
                        # 读4字节长度
                        len_buf = stream.read(4)
                        if len(len_buf) < 4:
                            break
                        length = int.from_bytes(len_buf, byteorder="big")

                        # 读实际数据
                        data1 = stream.read(length - 4)
                        if not data1:
                            break

                        # 检查签名
                        if data1[5:5+len(signature)] == signature:
                            return True
                        
            if len(payload) == 0x62:
                # 检查登录返回包特征
                signature = b'\x00\x00\x00\x62\x00\x03\x00\x00\x00\x01'
                if payload[:10] == signature and payload[14:20] == b'\x00\x00\x00\x00\x0a\x4e':
                    return True
                    
        except Exception as e:
            logger.debug(f"服务器识别失败: {e}")
            
        return False
        
    def _clear_tcp_cache(self):
        """清理TCP缓存"""
        self._data = b''
        self.tcp_next_seq = -1
        self.tcp_last_time = 0
        self.tcp_cache.clear()
        
    def _process_complete_packets(self):
        """处理完整的数据包"""
        while len(self._data) > 4:
            try:
                packet_size = struct.unpack('>I', self._data[:4])[0]
                
                if packet_size < 6 or packet_size > 0x0fffff:
                    self._data = b""
                    break

                if len(self._data) < packet_size:
                    if len(self._data) > self._cache_limit:
                        self._data = b""
                    break
                    
                # 提取完整数据包
                packet = self._data[:packet_size]
                self._data = self._data[packet_size:]
                
                # 分析数据包负载
                self._analyze_payload(packet, "TCP")
                
            except Exception as e:
                logger.debug(f"处理完整数据包失败: {e}")
                break
            
    def _analyze_payload(self, payload: bytes, protocol: str):
        """分析数据包负载"""
        if len(payload) < 4:
            return
            
        try:
            # 尝试解析为SyncContainerData
            parsed_data = self._parse_sync_container_data(payload)
            if parsed_data:
                self.sync_container_count += 1
                logger.debug(f"发现SyncContainerData数据包 #{self.sync_container_count}")
                
                if self.callback:
                    self.callback(parsed_data)
                    
        except Exception as e:
            logger.debug(f"解析数据包失败: {e}")
            
    def _parse_sync_container_data(self, payload: bytes) -> Optional[Dict[str, Any]]:
        """
        解析SyncContainerData数据包
        
        Args:
            payload: 原始数据包负载
            
        Returns:
            解析后的数据, 如果不是SyncContainerData则返回None
        """
        try:
            # 使用BinaryReader进行流式读取
            packets_reader = BinaryReader(payload)
            
            # 处理多个数据包
            while packets_reader.remaining() > 0:
                packet_size = packets_reader.peekUInt32()
                if packet_size < 6:
                    logger.debug("收到无效数据包")
                    return None
                    
                # 读取完整数据包
                packet_data = packets_reader.readBytes(packet_size)
                packet_reader = BinaryReader(packet_data)
                
                # 读取包长度和包类型
                packet_size = packet_reader.readUInt32()
                packet_type = packet_reader.readUInt16()
                
                # 解析包类型
                is_zstd_compressed = (packet_type & 0x8000) != 0
                msg_type_id = packet_type & 0x7fff
                
                # 根据消息类型处理
                if msg_type_id == 2:  # Notify
                    result = self._process_notify_msg(packet_reader, is_zstd_compressed)
                    if result:
                        return result
                elif msg_type_id == 6:  # FrameDown
                    result = self._process_frame_down_msg(packet_reader, is_zstd_compressed)
                    if result:
                        return result
                        
        except Exception as e:
            logger.debug(f"解析SyncContainerData失败: {e}")
            
        return None
        
    def _process_notify_msg(self, reader: BinaryReader, is_zstd_compressed: bool) -> Optional[Dict[str, Any]]:
        """处理Notify消息, 使用流式读取"""
        try:
            # 读取serviceUuid, stubId, methodId
            service_uuid = reader.readUInt64()
            stub_id = reader.readUInt32()
            method_id = reader.readUInt32()
            
            # 检查serviceUuid是否为游戏服务器标识
            GAME_SERVICE_UUID = 0x0000000063335342
            if service_uuid != GAME_SERVICE_UUID:
                logger.debug(f"跳过serviceId为 {service_uuid} 的NotifyMsg")
                return None
                
            logger.debug(f"methodId={method_id} isZstdCompressed={is_zstd_compressed}")
            
            # 读取剩余数据
            msg_payload = reader.readRemaining()
            
            # 解压缩
            if is_zstd_compressed:
                try:
                    msg_payload = self._decompress(msg_payload)
                    logger.debug(f"Notify解压缩成功, 解压缩后数据长度: {len(msg_payload)}")
                except Exception as e:
                    logger.debug(f"Notify zstd解压缩失败: {e}")
                    
            # 根据methodId处理
            SYNC_CONTAINER_DATA_METHOD = 0x00000015
            SyncNearEntities = 0x00000006
            SyncContainerDirtyData = 0x00000016
            SyncNearDeltaInfo = 0x0000002d
            SyncToMeDeltaInfo = 0x0000002e
            
            if method_id == SYNC_CONTAINER_DATA_METHOD:
                logger.debug('SyncContainerData数据包')
                logger.debug(f"发现SyncContainerData数据包 (serviceUuid: 0x{service_uuid:016x}, methodId: 0x{method_id:08x})")
                
                # 解析protobuf数据
                sync_data = SyncContainerData()
                sync_data.ParseFromString(msg_payload)
                
                # 通过回调函数传递数据，而不是直接处理
                if self.callback:
                    self.callback({'v_data': sync_data.VData})


            elif method_id == SyncNearEntities:
                logger.debug("发现SyncNearEntities数据包")
            elif method_id == SyncContainerDirtyData:
                logger.debug("发现SyncContainerDirtyData数据包")
            elif method_id == SyncNearDeltaInfo:
                logger.debug("发现SyncNearDeltaInfo数据包")
            elif method_id == SyncToMeDeltaInfo:
                logger.debug("发现SyncToMeDeltaInfo数据包")
            else:
                logger.debug(f"跳过methodId为 {method_id} 的NotifyMsg")
                
        except Exception as e:
            logger.debug(f"处理Notify消息失败: {e}")
            
        return None
        
    def _process_frame_down_msg(self, reader: BinaryReader, is_zstd_compressed: bool) -> Optional[Dict[str, Any]]:
        """处理FrameDown消息, 使用流式读取"""
        try:
            # 读取服务器序列号
            server_sequence_id = reader.readUInt32()
            
            if reader.remaining() == 0:
                return None
                
            # 读取嵌套数据包
            nested_packet = reader.readRemaining()
            
            # 解压缩
            if is_zstd_compressed:
                try:
                    nested_packet = self._decompress(nested_packet)
                    logger.debug(f"FrameDown解压缩成功, 解压缩后数据长度: {len(nested_packet)}")
                except Exception as e:
                    logger.debug(f"FrameDown zstd解压缩失败: {e}")
                    # 继续处理原始数据
                    
            logger.debug(f"处理FrameDown嵌套数据包, 服务器序列号: {server_sequence_id}")
            
            # 递归处理嵌套数据包
            return self._parse_sync_container_data(nested_packet)
            
        except Exception as e:
            logger.debug(f"处理FrameDown消息失败: {e}")
            
        return None

    def _cleanup_loop(self):
        """定时清理循环"""
        while self.is_running:
            try:
                time.sleep(10)  # 每10秒清理一次
                self._cleanup_expired_cache()
            except Exception as e:
                logger.debug(f"清理缓存时发生错误: {e}")
                
    def _cleanup_expired_cache(self):
        """清理过期的缓存"""
        FRAGMENT_TIMEOUT = 30  # 30秒超时
        
        with self.tcp_lock:
            current_time = time.time()
            
            # 清理过期的TCP缓存
            expired_seqs = []
            for seq in self.tcp_cache:
                if current_time - self.tcp_last_time > FRAGMENT_TIMEOUT:
                    expired_seqs.append(seq)
                    
            for seq in expired_seqs:
                del self.tcp_cache[seq]
                
            if expired_seqs:
                logger.debug(f"清理了 {len(expired_seqs)} 个过期的TCP缓存项")
                
            # 检查连接超时
            if self.tcp_last_time and current_time - self.tcp_last_time > FRAGMENT_TIMEOUT:
                logger.warning("다음 패킷을 받지 못했습니다. seq=%s", self.tcp_next_seq)
                self.current_server = ''
                self._clear_tcp_cache()
