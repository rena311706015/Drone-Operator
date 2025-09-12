<img width="604" height="226" alt="image 9" src="https://github.com/user-attachments/assets/48e541f7-3413-4dc7-8558-4192fc1e5eee" />  

網頁裡列出所有 Drone，每台 Drone 可以選擇蒐集座標和蒐集電池兩種 Mission  
Start Mission 後，根據 CRD 建立一個 CR，CRD 的 Operator 執行以下流程  

1. 先進行健康檢查，健康狀態有兩種
   - 正常，則執行勾選的任務  
      勾選的任務皆執行完成後，清理 CR 和它 own 的所有 Job (包含健康檢查與勾選的任務，最多會有三個 Job)
   - 異常，則更新狀態為 Malfunction，直接清理 CR  和它 own 的健康檢查 Job  
2. 過程中檢測到的座標、電池資料存入 Postgres  

## 啟用步驟

1. 將此專案 clone 到本地端  
2. 啟動 minikube  
   `minikube start`  
3. 切換到 minikube Docker  
   `eval $(minikube docker-env)`  
4. 進入 missions 資料夾後 build Docker Image    
   `docker build -t drone-worker:v1 .`  
5. apply CloudNativePG 提供的 Postgres Operator  
   `kubectl apply --server-side -f \  
   https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.27/releases/cnpg-1.27.0.yaml`  
6. 確認 Postgres 相關 CRD 存在後，回到根目錄一次 apply Drone CRD、Drone Operator、和 Postgres CR 到 minikube 中  
   `kubectl apply -f .`     

## 驗證步驟

1. 檢查當前 Docker 環境下是否存在 drone-worker 的 image  
   `docker images`  
2. 建議開啟四個終端機
   - 一個監控 minikube 中 Pod 的變化，先檢查是否已經有 drone-operator 和 drone-pg-cluster 兩個 Pod  
      `kubectl get pods -w` 
   - 一個監控 DroneMission 這個 CRD 的 CR 變化  
      `kubectl get DroneMission -w` 
   - 一個開啟 API Server
      `python api_server.py` 
   - 一個進入 Postgres 的 console
      `kubectl get secret drone-pg-cluster-app -o jsonpath="{.data.password}" | base64 --decode`  
      複製顯示的密碼後  
      `kubectl exec -ti -n default drone-pg-cluster-1 -- psql -U app -d dronedata -h localhost -W`  
      然後手動建立資料表
      `CREATE TABLE IF NOT EXISTS coordinates (
         id SERIAL PRIMARY KEY,
         drone_id VARCHAR(50),
         latitude FLOAT,
         longitude FLOAT,
         created_at TIMESTAMP DEFAULT NOW()
      );`  
      `CREATE TABLE IF NOT EXISTS battery_logs (
         id SERIAL PRIMARY KEY,
         drone_id VARCHAR(50),
         battery_level INT,
         created_at TIMESTAMP DEFAULT NOW()
      );`  
3. 雙擊 index.html 開啟網頁前端 
4. 網頁隨便勾選一個 Drone 的任務後 Start Mission  
5. 觀察監控 Pod 和 監控 DroneMission 的兩個終端機  
6. 當看到網頁 Drone 顯示 Mulfunction 或結束任務回到 Idle 狀態後，停止當前監控並重新執行  
   `kubectl get pods` 和 `kubectl get DroneMission`  
   預期會看到原本啟動的 Job 和 CR 都被清理  
   <div style="display:flex; gap:10px;">
     <img src="https://github.com/user-attachments/assets/3e067fb6-0337-48c7-8cfe-e86a28c7230f" alt="image 10" style="width:33%; height:auto;" />
     <img src="https://github.com/user-attachments/assets/8159dc78-394d-45e3-9faa-aaf60c0eeefa" alt="image 11" style="width:60%; height:auto;" />
   </div>
7. 切換到 DB console 後查詢資料表   
   `SELECT * FROM battery_logs;`  
   `SELECT * FROM coordinates;`
   <div style="display:flex; gap:10px; align-items:flex-start;">
     <img src="https://github.com/user-attachments/assets/35098d5b-1674-4e7b-8da3-16ff8d47a001" alt="image 12" style="width:40%; height:auto;" />
     <img src="https://github.com/user-attachments/assets/aa8e526c-2412-435d-8fc1-ab6e6a09de9b" alt="image 13" style="width:50%; height:auto;" />
   </div>


