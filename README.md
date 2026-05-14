# Agentic Predictive Cloud Failover System

A "Git-like" state-synchronizing predictive failover architecture for cloud infrastructures. This project demonstrates how an intelligent agentic router can monitor live cloud telemetry, predict impending downtime using Machine Learning heuristics, and instantly route user traffic to a local backup environment—ensuring zero downtime.

## 🌟 Key Features

- **Real-Time Telemetry Streaming**: A lightweight agent runs on the cloud infrastructure to report live CPU and Memory metrics.
- **Predictive ML Router**: An intelligent local gateway analyzes telemetry trends to calculate downtime probability in real-time.
- **Zero-Downtime Failover**: Traffic is seamlessly shifted to a local simulated infrastructure the moment a crash is predicted.
- **Visual Presentation Dashboards**: 
  - A fully functional **LeetCode Clone** to serve as the user-facing application.
  - A beautiful **Admin Dashboard** (powered by Chart.js) to visualize live CPU loads and ML predictions.
- **Automated Stress Testing**: A built-in Python script to gradually overwhelm the cloud server and simulate a hard crash.

---

## 🏗️ Architecture & Components

The system is composed of several independent micro-components:

| File / Component | Description |
| :--- | :--- |
| `main.tf` | Terraform configuration to automatically provision the primary AWS EC2 infrastructure and security groups. |
| `telemetry_server.py` | Python HTTP agent running on the AWS instance that exposes real-time `psutil` system metrics. |
| `local_router.py` | **The Brain.** Acts as a reverse proxy, continuously polls telemetry, calculates failure probability, and acts as the failover switch. |
| `local_simulated_ec2.py` | The local backup environment. Serves the application when the AWS cloud is predicted to go offline. |
| `stress1.py` | A multi-processing stress script deployed to AWS to artificially spike CPU load and ultimately kill the NGINX web server. |
| `index.html` | The user-facing LeetCode clone application. Features real-time Javascript latency detection. |
| `admin_dashboard.html` | A sleek analytics dashboard to visualize the failover pipeline in action. |

---

## 🚀 How to Run the Demonstration

To present this project to judges or stakeholders, follow this exact workflow:

### 1. Start the Local Infrastructure
Open two separate terminal windows on your local machine to start the backup data center and the intelligent router.

**Terminal 1 (Local Backup):**
```bash
python local_simulated_ec2.py
```
*(Runs on port 8082)*

**Terminal 2 (AI Predictor & Router):**
```bash
python local_router.py
```
*(Runs on port 8090)*

### 2. Open the Dashboards
Open your browser and arrange two tabs side-by-side:
- **The User Experience:** Navigate to `http://localhost:8090`. This is the LeetCode application.
- **The Admin/Judge View:** Navigate to `http://localhost:8090/admin`. This is the live telemetry chart.

### 3. Simulate the Cloud Crash
In a third terminal, SSH into your AWS EC2 instance and trigger the gradual stress test:

**Terminal 3 (AWS SSH):**
```bash
ssh -i cloud-failover-key.pem ubuntu@<AWS_IP_ADDRESS> "python3 stress1.py --gradual"
```

### 4. Watch the Magic Happen
1. Observe the **Admin Dashboard**. You will see the AWS CPU metric begin to climb.
2. The **ML Probability** line will follow the CPU trend.
3. Once the probability hits **90%**, the Router will instantly flash RED and shift routing to the local simulation.
4. On the AWS server, the stress script will hit 100% and completely crash the NGINX web server.
5. Look at the **User Experience (LeetCode)** tab. Because the router intercepted the failure early, the user experiences absolutely **zero downtime**. A green "LOCAL FAILOVER ACTIVE" badge will appear to prove the traffic shifted locally.

---

## 🛠️ Manual Cloud Recovery
Because the system simulates a catastrophic hard crash, the AWS web server stays dead to prove the failover works permanently. To recover the cloud infrastructure for another test:

```bash
ssh -i cloud-failover-key.pem ubuntu@<AWS_IP_ADDRESS> "sudo systemctl start nginx"
```
The ML Predictor will instantly detect the recovery, sync the state, and silently route traffic back to the AWS Cloud.
