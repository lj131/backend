"""
WebRTC信令服务器处理模块
基于aiortc实现P2P语音通话
"""
import asyncio
import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_candidate_sdp(candidate_str: str, sdpMid=None, sdpMLineIndex=None):
    """
    解析 SDP candidate 字符串为 aiortc RTCIceCandidate。

    SDP 候选格式示例:
        candidate:1 1 UDP 2122252543 192.168.1.1 54321 typ host
        candidate:2 1 UDP 2122252543 192.168.1.1 54322 typ srflx raddr 10.0.0.1 rport 12345
    """
    if not candidate_str:
        return None

    parts = candidate_str.split()
    if len(parts) < 8:
        logger.warning(f"Invalid candidate SDP string: {candidate_str}")
        return None

    try:
        # candidate:<foundation> <component> <protocol> <priority> <ip> <port> typ <type> ...
        foundation = parts[0].split(":")[1] if ":" in parts[0] else parts[0]
        component = int(parts[1])
        protocol = parts[2].lower()
        priority = int(parts[3])
        ip = parts[4]
        port = int(parts[5])
        # parts[6] should be "typ"
        candidate_type = parts[7] if len(parts) > 7 else "host"

        related_address = None
        related_port = None
        tcp_type = None

        # 解析可选字段
        i = 8
        while i < len(parts) - 1:
            if parts[i] == "raddr":
                related_address = parts[i + 1]
                i += 2
            elif parts[i] == "rport":
                related_port = int(parts[i + 1])
                i += 2
            elif parts[i] == "tcptype":
                tcp_type = parts[i + 1]
                i += 2
            else:
                i += 1

        return RTCIceCandidate(
            component=component,
            foundation=foundation,
            ip=ip,
            port=port,
            priority=priority,
            protocol=protocol,
            type=candidate_type,
            relatedAddress=related_address,
            relatedPort=related_port,
            sdpMid=sdpMid,
            sdpMLineIndex=sdpMLineIndex,
            tcpType=tcp_type,
        )
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse candidate SDP: {candidate_str}, error: {e}")
        return None


@dataclass
class CallSession:
    """通话会话信息"""
    call_id: str
    user_id: str
    character_id: str
    peer_connection: RTCPeerConnection
    created_at: float
    active: bool = False
    audio_tracks: list = None

    def __post_init__(self):
        if self.audio_tracks is None:
            self.audio_tracks = []

class WebRTCAgent:
    """WebRTC信令处理器"""

    def __init__(self):
        self.connections: Dict[str, RTCPeerConnection] = {}
        self.call_sessions: Dict[str, CallSession] = {}
        self.data_channels: Dict[str, RTCDataChannel] = {}

    async def handle_offer(self, websocket, offer_data: dict, user_id: str, character_id: str):
        """处理WebRTC offer"""
        try:
            # 创建PeerConnection
            pc = RTCPeerConnection()
            self.connections[websocket] = pc

            # 创建唯一通话ID
            call_id = str(uuid.uuid4())

            # 配置音频轨道
            # 注意：这里暂时不添加本地音频流，因为我们只需要接收用户音频
            # 添加音频接收轨道
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
                if track.kind == "audio":
                    call_session = self.call_sessions.get(call_id)
                    if call_session:
                        call_session.audio_tracks.append(track)

            # 处理ICE候选
            @pc.on("icecandidate")
            def on_icecandidate(candidate):
                if candidate:
                    # 发送ICE候选给前端
                    candidate_data = {
                        "type": "ice_candidate",
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                        "call_id": call_id
                    }
                    asyncio.create_task(websocket.send_text(json.dumps(candidate_data)))

            # 处理连接状态变化
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                state = pc.connectionState
                logger.info(f"Connection state: {state} (call_id={call_id})")

                # 发送状态更新（WebSocket 可能已关闭，捕获异常）
                try:
                    status_data = {
                        "type": "connection_state",
                        "state": state,
                        "call_id": call_id,
                    }
                    await websocket.send_text(json.dumps(status_data))
                except Exception:
                    pass  # WebSocket 已断开，无需发送

                # 连接成功
                if state == "connected":
                    call_session = self.call_sessions.get(call_id)
                    if call_session:
                        call_session.active = True

            # 设置远程描述
            offer = RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["type"])
            await pc.setRemoteDescription(offer)

            # 创建answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # 创建通话会话
            call_session = CallSession(
                call_id=call_id,
                user_id=user_id,
                character_id=character_id,
                peer_connection=pc,
                created_at=asyncio.get_event_loop().time()
            )
            self.call_sessions[call_id] = call_session

            # 发送answer给前端（type 既是消息类型也是 SDP 类型，值均为 "answer"）
            response = {
                "type": pc.localDescription.type,  # SDP type: "answer"
                "sdp": pc.localDescription.sdp,
                "call_id": call_id
            }

            return response

        except Exception as e:
            logger.error(f"Error handling offer: {e}")
            raise

    async def handle_answer(self, websocket, answer_data: dict, call_id: str):
        """处理WebRTC answer"""
        try:
            call_session = self.call_sessions.get(call_id)
            if not call_session:
                raise ValueError(f"Call session {call_id} not found")

            pc = call_session.peer_connection

            # 设置远程描述
            answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
            await pc.setRemoteDescription(answer)

            return {"type": "answer_accepted", "call_id": call_id}

        except Exception as e:
            logger.error(f"Error handling answer: {e}")
            raise

    async def handle_ice_candidate(self, websocket, candidate_data: dict, call_id: str):
        """处理ICE候选"""
        try:
            call_session = self.call_sessions.get(call_id)
            if not call_session:
                raise ValueError(f"Call session {call_id} not found")

            pc = call_session.peer_connection

            # 前端发送的 candidate 是 SDP 候选字符串
            # 格式: candidate:<foundation> <component> <protocol> <priority> <ip> <port> typ <type>
            candidate_str = candidate_data.get("candidate", "")
            sdp_mid = candidate_data.get("sdpMid")
            sdp_mline_index = candidate_data.get("sdpMLineIndex")

            # 解析 SDP 候选字符串为 RTCIceCandidate
            ice_candidate = _parse_candidate_sdp(
                candidate_str,
                sdpMid=sdp_mid,
                sdpMLineIndex=sdp_mline_index,
            )

            if ice_candidate:
                await pc.addIceCandidate(ice_candidate)

            return {"type": "ice_candidate_handled", "call_id": call_id}

        except Exception as e:
            logger.error(f"Error handling ICE candidate: {e}")
            raise

    async def handle_audio_data(self, websocket, audio_data: dict, call_id: str):
        """处理音频数据（预留功能）"""
        try:
            call_session = self.call_sessions.get(call_id)
            if not call_session or not call_session.active:
                return {"type": "error", "message": "Call session not active"}

            # 这里可以处理音频数据，比如转发给TTS服务
            # 目前只是记录日志
            logger.info(f"Received audio data for call {call_id}")

            return {"type": "audio_data_received", "call_id": call_id}

        except Exception as e:
            logger.error(f"Error handling audio data: {e}")
            raise

    async def end_call(self, websocket, call_id: str):
        """结束通话"""
        try:
            call_session = self.call_sessions.get(call_id)
            if call_session:
                # 关闭PeerConnection
                await call_session.peer_connection.close()

                # 从会话列表中移除
                del self.call_sessions[call_id]

            # 从连接列表中移除
            if websocket in self.connections:
                del self.connections[websocket]

            return {"type": "call_ended", "call_id": call_id}

        except Exception as e:
            logger.error(f"Error ending call: {e}")
            raise

    async def get_call_status(self, call_id: str):
        """获取通话状态"""
        call_session = self.call_sessions.get(call_id)
        if not call_session:
            return {"type": "error", "message": "Call session not found"}

        return {
            "type": "call_status",
            "call_id": call_id,
            "active": call_session.active,
            "user_id": call_session.user_id,
            "character_id": call_session.character_id,
            "created_at": call_session.created_at,
            "connection_state": call_session.peer_connection.connectionState
        }

# 全局WebRTC实例
webrtc_agent = WebRTCAgent()