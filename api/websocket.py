"""
WebSocket端点
处理WebRTC信令和实时语音通话
"""
import asyncio
import json
import logging
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect, APIRouter

from funcation.webrtc_agent import webrtc_agent
from funcation.conversation_manager import conversation_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# 活跃WebSocket连接
active_connections: Dict[int, WebSocket] = {}


@router.websocket("/voice/call")
async def websocket_voice_call(websocket: WebSocket):
    """语音通话WebSocket端点"""
    await websocket.accept()
    connection_id = id(websocket)
    active_connections[connection_id] = websocket

    async def _safe_send(data: dict):
        """安全发送消息，忽略 WebSocket 已关闭的情况"""
        try:
            await websocket.send_text(json.dumps(data))
        except RuntimeError as e:
            if "close message has been sent" not in str(e):
                raise
        except WebSocketDisconnect:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")
            call_id = message.get("call_id")

            # 非 ping 消息都打印日志
            if msg_type != "ping":
                logger.info("[VOICE WS] 收到: type=%s call_id=%s keys=%s",
                            msg_type, call_id, list(message.keys()))

            try:
                if msg_type == "offer":
                    logger.info("[VOICE WS] → handle_offer char=%s",
                                message.get("character_id", "?"))
                    resp = await webrtc_agent.handle_offer(
                        websocket=websocket,
                        offer_data=message.get("offer"),
                        user_id=message.get("user_id", "default"),
                        character_id=message.get("character_id", "default"),
                    )
                    logger.info("[VOICE WS] ← handle_offer 返回: %s",
                                {k: v for k, v in resp.items() if k != "sdp"})
                    await _safe_send(resp)

                elif msg_type == "answer":
                    resp = await webrtc_agent.handle_answer(
                        websocket=websocket,
                        answer_data=message.get("answer"),
                        call_id=call_id,
                    )
                    await _safe_send(resp)

                elif msg_type == "ice_candidate":
                    resp = await webrtc_agent.handle_ice_candidate(
                        websocket=websocket,
                        candidate_data=message,
                        call_id=call_id,
                    )
                    await _safe_send(resp)

                elif msg_type == "start_conversation":
                    logger.info("[VOICE WS] → start_conversation call_id=%s char=%s",
                                call_id, message.get("character_id", "?"))
                    ok = await conversation_manager.start_conversation(
                        call_id=call_id,
                        character_id=message.get("character_id"),
                        user_id=message.get("user_id"),
                        websocket=websocket,
                    )
                    logger.info("[VOICE WS] ← start_conversation 返回: ok=%s", ok)
                    await _safe_send({
                        "type": "conversation_started",
                        "call_id": call_id,
                        "success": ok,
                    })

                elif msg_type == "audio_data":
                    raw = message.get("audio_data", "")
                    audio_bytes = raw.encode() if isinstance(raw, str) else raw
                    resp = await conversation_manager.process_audio(call_id, audio_bytes)
                    await _safe_send(resp)

                elif msg_type == "text_message":
                    text = message.get("text", "")
                    logger.info("[VOICE WS] → text_message: '%s'", text[:80])
                    resp = await conversation_manager.process_text_message(
                        call_id=call_id,
                        user_message=text,
                    )
                    logger.info("[VOICE WS] ← text_message 处理完成 type=%s", resp.get("type"))
                    await _safe_send(resp)

                elif msg_type == "get_status":
                    resp = await webrtc_agent.get_call_status(call_id)
                    await _safe_send(resp)

                elif msg_type == "conversation_status":
                    resp = await conversation_manager.get_conversation_status(call_id)
                    await _safe_send(resp)

                elif msg_type == "end_call":
                    logger.info("[VOICE WS] → end_call call_id=%s", call_id)
                    await webrtc_agent.end_call(websocket, call_id)
                    await conversation_manager.end_conversation(call_id)
                    await _safe_send({
                        "type": "call_ended",
                        "call_id": call_id,
                    })

                elif msg_type == "ping":
                    await _safe_send({
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time(),
                    })

                else:
                    logger.warning("[VOICE WS] 未知消息类型: %s", msg_type)
                    await _safe_send({
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}",
                    })

            except Exception as exc:
                logger.error("[VOICE WS] 处理消息失败: %s", exc)
                await _safe_send({
                    "type": "error",
                    "message": str(exc),
                    "call_id": call_id,
                })

    except WebSocketDisconnect:
        logger.info("WebSocket 断开: %d", connection_id)
    except Exception as exc:
        logger.error("WebSocket 错误: %s", exc)
    finally:
        if connection_id in active_connections:
            del active_connections[connection_id]


@router.websocket("/voice/status")
async def websocket_status(websocket: WebSocket):
    """状态监控WebSocket —— 每秒推送系统状态"""
    await websocket.accept()
    try:
        while True:
            status = {
                "active_connections": len(active_connections),
                "timestamp": asyncio.get_event_loop().time(),
            }
            await websocket.send_text(json.dumps(status))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Status WebSocket 断开")
    except Exception as exc:
        logger.error("Status WebSocket 错误: %s", exc)
