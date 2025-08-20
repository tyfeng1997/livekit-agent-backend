# backend_server.py
from flask import Flask, request, jsonify
import subprocess
import os
import threading
import time
import logging
from typing import Dict, Optional

app = Flask(__name__)
logger = logging.getLogger(__name__)

# 存储运行中的 agent 进程
running_agents: Dict[str, subprocess.Popen] = {}

class AgentManager:
    def __init__(self):
        self.agents = {}
        self.lock = threading.Lock()
    
    def start_agent(self, client_id: str, config: dict) -> bool:
        """为特定客户启动 agent"""
        with self.lock:
            if client_id in self.agents:
                logger.warning(f"Agent for client {client_id} already exists")
                return False
            
            try:
                # 构造启动命令
                cmd = [
                    "python", "parameterized_agent.py",  # 修改为你的脚本名称
                    "--client-id", client_id,
                    "--instructions", config.get("instructions", ""),
                    "--transfer-to", config.get("transfer_to", ""),
                    "--client-name", config.get("client_name", ""),
                    "--agent-name", config.get("agent_name", "inbound-agent"),
                ]
                
                # 添加环境变量
                env = os.environ.copy()
                if "livekit_url" in config:
                    env["LIVEKIT_URL"] = config["livekit_url"]
                if "api_key" in config:
                    env["LIVEKIT_API_KEY"] = config["api_key"]
                if "api_secret" in config:
                    env["LIVEKIT_API_SECRET"] = config["api_secret"]
                
                # 启动进程
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                self.agents[client_id] = {
                    "process": process,
                    "config": config,
                    "start_time": time.time()
                }
                
                logger.info(f"Agent started for client {client_id}, PID: {process.pid}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start agent for {client_id}: {e}")
                return False
    
    def stop_agent(self, client_id: str) -> bool:
        """停止特定客户的 agent"""
        with self.lock:
            if client_id not in self.agents:
                return False
            
            try:
                process = self.agents[client_id]["process"]
                process.terminate()
                
                # 等待进程结束，如果超时则强制杀死
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                del self.agents[client_id]
                logger.info(f"Agent stopped for client {client_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop agent for {client_id}: {e}")
                return False
    
    def get_agent_status(self, client_id: str) -> Optional[dict]:
        """获取 agent 状态"""
        with self.lock:
            if client_id not in self.agents:
                return None
            
            agent_info = self.agents[client_id]
            process = agent_info["process"]
            
            return {
                "client_id": client_id,
                "pid": process.pid,
                "status": "running" if process.poll() is None else "stopped",
                "start_time": agent_info["start_time"],
                "config": agent_info["config"]
            }
    
    def list_agents(self) -> list:
        """列出所有 agent"""
        with self.lock:
            return [self.get_agent_status(cid) for cid in self.agents.keys()]

# 全局 agent 管理器
agent_manager = AgentManager()

@app.route('/agent/start', methods=['POST'])
def start_agent():
    """启动 agent 的 API 端点"""
    data = request.json
    client_id = data.get('client_id')
    config = data.get('config', {})
    
    if not client_id:
        return jsonify({"error": "client_id is required"}), 400
    
    success = agent_manager.start_agent(client_id, config)
    
    if success:
        return jsonify({"message": f"Agent started for client {client_id}"}), 200
    else:
        return jsonify({"error": "Failed to start agent"}), 500

@app.route('/agent/stop', methods=['POST'])
def stop_agent():
    """停止 agent 的 API 端点"""
    data = request.json
    client_id = data.get('client_id')
    
    if not client_id:
        return jsonify({"error": "client_id is required"}), 400
    
    success = agent_manager.stop_agent(client_id)
    
    if success:
        return jsonify({"message": f"Agent stopped for client {client_id}"}), 200
    else:
        return jsonify({"error": "Agent not found or failed to stop"}), 404

@app.route('/agent/status/<client_id>', methods=['GET'])
def get_agent_status(client_id):
    """获取特定 agent 的状态"""
    status = agent_manager.get_agent_status(client_id)
    
    if status:
        return jsonify(status), 200
    else:
        return jsonify({"error": "Agent not found"}), 404

@app.route('/agent/list', methods=['GET'])
def list_agents():
    """列出所有 agent"""
    agents = agent_manager.list_agents()
    return jsonify({"agents": agents}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)