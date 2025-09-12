import kopf
import kubernetes
import datetime
import base64
import random
from kubernetes import client

EXIT_CODES = {}

def get_exit_code(drone_id):
    global EXIT_CODES

    if drone_id not in EXIT_CODES:
        EXIT_CODES[drone_id] = None

    if EXIT_CODES[drone_id] is None:
        EXIT_CODES[drone_id] = random.randint(0, 1)

    return EXIT_CODES[drone_id]

def reset_exit_code(drone_id):
    global EXIT_CODES
    EXIT_CODES[drone_id] = None

# 與 ConfigMap 的 data: operator.py: 一致
# --- 初始化 API Client ---
def get_k8s_apis():
    try:
        kubernetes.config.load_incluster_config()
    except kubernetes.config.ConfigException:
        kubernetes.config.load_kube_config()

    return {
        'batch': client.BatchV1Api(),
        'core': client.CoreV1Api(),
        'custom': client.CustomObjectsApi(),
    }

# === 創建 CR 時觸發 ===
@kopf.on.create('drone.example.com', 'v1', 'dronemissions')
def create_mission(spec, name, namespace, uid, logger, patch, **kwargs):
    apis = get_k8s_apis()
    drone_id = spec.get('droneId')
    logger.info(f"New mission request for {drone_id}. Starting health check.")

    # --- 建立 Health Check Job ---
    health_job_name = f"health-check-{name}"
    create_mission_job(
        apis, name, namespace, uid, health_job_name, drone_id,
        'python /app/health_check.py'
    )
    # --- 更新 CR 狀態 ---
    patch.status['phase'] = "HealthChecking"
    patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
    patch.status['healthCheckJob'] = health_job_name

    return {"message": f"Health check job {health_job_name} created for {drone_id}."}

# === 定期檢查任務狀態 ===
@kopf.timer('drone.example.com', 'v1', 'dronemissions', interval=1.0)
def reconcile_missions(spec, status, name, namespace, uid, logger, patch, **kwargs):
    apis = get_k8s_apis()
    phase = status.get('phase')
    drone_id = spec.get('droneId')

    # --- 狀態 1: 健康檢查 ---
    if phase == 'HealthChecking':
        job_name = status.get('healthCheckJob')

        try:
            # 找出這個 job 的 Pod
            pod_list = apis['core'].list_namespaced_pod(
                namespace=namespace,
                label_selector=f"job-name={job_name}"
            )

            if not pod_list.items:
                logger.info(f"No pods yet for job {job_name}, skipping.")
                return

            pod = pod_list.items[0]
            cs = pod.status.container_statuses
            if not cs or not cs[0].state.terminated:
                logger.info(f"Pod for {job_name} still running.")
                return

            # exit_code = cs[0].state.terminated.exit_code
            exit_code = get_exit_code(drone_id)
            if exit_code == 0:
                logger.info(f"Health check for {drone_id} Succeeded. Starting mission jobs.")

                # --- 讀取 DB Secret ---
                secret = apis['core'].read_namespaced_secret(name='drone-pg-cluster-app', namespace=namespace)
                db_host = base64.b64decode(secret.data['host']).decode('utf-8')
                db_name = base64.b64decode(secret.data['dbname']).decode('utf-8')
                db_user = base64.b64decode(secret.data['user']).decode('utf-8')
                db_password = base64.b64decode(secret.data['password']).decode('utf-8')

                # --- 建立 Mission Jobs ---
                mission_jobs = []
                if spec.get('collectCoordinates'):
                    coord_job_name = f"coord-mission-{name}"
                    mission_jobs.append(coord_job_name)
                    create_mission_job(
                        apis, name, namespace, uid, coord_job_name, drone_id,
                        'python /app/collect_coords.py', db_host, db_name, db_user, db_password
                    )

                if spec.get('collectBattery'):
                    battery_job_name = f"battery-mission-{name}"
                    mission_jobs.append(battery_job_name)
                    create_mission_job(
                        apis, name, namespace, uid, battery_job_name, drone_id,
                        'python /app/collect_battery.py', db_host, db_name, db_user, db_password
                    )
                if not mission_jobs:
                    logger.info(f"{drone_id} finish health checking, turning status to Idle...")
                    patch.status['phase'] = "Succeeded"
                    patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
                else: 
                    # --- 更新 CR phase 為 InMission ---
                    patch.status['phase'] = "InMission"
                    patch.status['missionJobs'] = mission_jobs
                    patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
            else:
                logger.warning(f"Health check for {drone_id} FAILED. Drone is malfunctioning.")
                patch.status['phase'] = "Malfunctioning"
                patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
        except client.ApiException as e:
            logger.warning(f"Health check job not ready: {e}")
    # --- 狀態 2: InMission，檢查所有 Job ---
    elif phase == 'InMission':
        mission_jobs = status.get('missionJobs', [])
        # 將 Health Check Job 加入檢查
        all_jobs = mission_jobs + [status.get('healthCheckJob')]
        completed_count = 0

        for job_name in all_jobs:
            try:
                job = apis['batch'].read_namespaced_job_status(name=job_name, namespace=namespace)
                if job.status.succeeded:
                    completed_count += 1
                elif job.status.failed:
                    patch.status['phase'] = "Failed"
                    patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
                    return
            except client.ApiException:
                # Job 還不存在或被刪掉，忽略
                continue

        # 如果所有 Job 都完成
        if completed_count == len(all_jobs):
            logger.info(f"All jobs for {drone_id} completed. Deleting CR (cleanup).")
            patch.status['phase'] = "Succeeded"
            patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"

    # --- 狀態 3: 清理 CR ---
    elif phase in ['Succeeded', 'Failed', 'Malfunctioning']:  
        logger.info(f"Mission for {drone_id} ended with phase '{phase}'. Cleaning up CR.")
        patch.status['lastUpdateTime'] = datetime.datetime.utcnow().isoformat() + "Z"
        reset_exit_code(drone_id)
        try:
            apis['custom'].delete_namespaced_custom_object(
                group="drone.example.com", version="v1",
                name=name, namespace=namespace, plural="dronemissions",
                body=client.V1DeleteOptions()
            )
        except client.ApiException as e:
            logger.warning(f"CR delete failed or already deleted: {e}")
    

# === 建立任務 Job 函式 ===
def create_mission_job(apis, cr_name, namespace, uid, job_name,
                       drone_id, command=None, db_host=None, db_name=None, db_user=None, db_password=None):
    job_obj = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "ownerReferences": [{
                "apiVersion": "drone.example.com/v1",
                "kind": "DroneMission",
                "name": cr_name,
                "uid": uid,
                "controller": True,
                "blockOwnerDeletion": True,
            }],
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "mission-runner",
                            "image": "drone-worker:v1",
                            "command": ["/bin/bash", "-c"],
                            "args": [command],
                            "env": [
                                {"name": "DRONE_ID", "value": drone_id},
                                {"name": "POSTGRES_HOST", "value": db_host},
                                {"name": "POSTGRES_DB", "value": db_name},
                                {"name": "POSTGRES_USER", "value": db_user},
                                {"name": "POSTGRES_PASSWORD", "value": db_password},
                            ],
                        }
                    ],
                    "restartPolicy": "Never",
                }
            },
            "backoffLimit": 0,
        },
    }

    apis['batch'].create_namespaced_job(namespace=namespace, body=job_obj)