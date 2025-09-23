from flask import Flask, request, jsonify
from flask_cors import CORS
from kubernetes import client, config
import random
import string
import datetime

app = Flask(__name__)
CORS(app) # 允許跨域請求

# 初始的無人機列表
DRONES = {
    "D01": {"status": "Idle", "last_update_time": None},
    "D02": {"status": "Idle", "last_update_time": None},
    "D03": {"status": "Idle", "last_update_time": None},
}
# 全域記憶體快取，保存最後一次狀態
LAST_STATUSES = {}

def get_k8s_api():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CustomObjectsApi()

@app.route('/drones', methods=['GET'])
def get_drone_statuses():
    api = get_k8s_api()
    
    # 建立一個當前回應的狀態副本
    current_statuses = {drone_id: {"status": "Idle", "last_update_time": ""} for drone_id in DRONES}
    
    # 從 K8s 查詢所有活躍的 DroneMission CRs
    try:
        cr_list = api.list_namespaced_custom_object(
            group="drone.example.com",
            version="v1",
            namespace="default",
            plural="dronemissions"
        ) 
        active_drones = set()
        for cr in cr_list.get('items', []):
            drone_id = cr['spec'].get('droneId')
            if drone_id in current_statuses:
                phase = cr.get('status', {}).get('phase', 'Pending')
                
                # 轉換 CR Phase 為前端顯示的 Status
                status_map = {
                    "Pending": "Pending",
                    "HealthChecking": "Checking...",
                    "InMission": "In Mission",
                    "Succeeded": "Mission Succeeded",
                    "Failed": "Mission Failed",
                    "Malfunctioning": "Malfunction",
                    "Idle": "Idle"
                }
                
                status_value = status_map.get(phase, "Unknown")
                update_time = cr.get('status', {}).get('lastUpdateTime', '')

                current_statuses[drone_id]['status'] = status_map.get(phase, "Unknown")
                current_statuses[drone_id]['last_update_time'] = cr.get('status', {}).get('lastUpdateTime', '')
                
                # 更新快取
                LAST_STATUSES[drone_id] = {
                    "status": status_value,
                    "last_update_time": update_time
                }
                active_drones.add(drone_id)

        for drone_id in current_statuses:
            if drone_id not in active_drones and drone_id in LAST_STATUSES:
                if current_statuses[drone_id]['status'] != LAST_STATUSES[drone_id]['status']:
                    current_statuses[drone_id] = LAST_STATUSES[drone_id]

    except client.ApiException as e:
        print(f"Error fetching CRs: {e}")
        # 如果無法連接 K8s API，至少回傳基本列表
        pass

    # 格式化成前端需要的陣列
    response_data = [
        {"droneId": drone_id, "status": data["status"], "lastUpdateTime": data["last_update_time"]}
        for drone_id, data in current_statuses.items()
    ]
    return jsonify(response_data)

@app.route('/mission', methods=['POST'])
def create_mission():
    data = request.get_json()
    drone_id = data.get('droneId')
    if not drone_id or drone_id not in DRONES:
        return jsonify({"error": "Invalid droneId"}), 400

    api = get_k8s_api()
    
    # 產生一個唯一的 CR 名稱
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    cr_name = f"dm-{drone_id.lower()}-{random_suffix}"

    custom_resource = {
        "apiVersion": "drone.example.com/v1",
        "kind": "DroneMission",
        "metadata": {
            "name": cr_name,
        },
        "spec": {
            "droneId": drone_id,
            "collectCoordinates": data.get('collectCoordinates', False),
            "collectBattery": data.get('collectBattery', False),
        },
    }
    print(f"{drone_id} Coordinates: {data.get('collectCoordinates', False)}, Battery: {data.get('collectBattery', False)}")
    try:
        api.create_namespaced_custom_object(
            group="drone.example.com",
            version="v1",
            namespace="default",
            plural="dronemissions",
            body=custom_resource,
        )
        return jsonify({"message": "Mission created", "cr_name": cr_name}), 201
    except client.ApiException as e:
        return jsonify({"error": f"Failed to create Kubernetes resource: {e.reason}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)