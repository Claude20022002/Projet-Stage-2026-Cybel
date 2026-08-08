# CYBEL Project \- ICRA

### 

### 

### **Step 1: Scientific Positioning & Title Reframing**

* **Objective:** Move away from a project-style "internship report" title toward a problem-oriented, methodological contribution.  
* **ICRA Title: example**  
  *Reclaiming Closed Service Robots: A Hypothesis-Driven Methodology for Non-Destructive Protocol Reconstruction*  
* **Abstract Structure:**  
  1. **Context & Problem:** Commercial Android-ROS service robots operate as dual-computing black boxes without public APIs, creating an "Execution Gap" where transport success does not equal physical execution.  
  2. **Core Contribution:** A reproducible, 7-phase non-destructive reverse-engineering methodology (C1) and lightweight edge middleware architecture (C3).  
  3. **Empirical Validation:** Triangulation across 4 falsifiable hypotheses (H1–H4), 455 ROS topics, 308 ROS services, REST latency under 100 ms, and a 100% guided-tour completion rate.  
     

### **Step 2: Introduction & Problem Formalization**

1. **Define the Structural Barriers:**  
   * *Vantage Point Fragmentation:* Neither network packets, static APK analysis, nor ROS introspection alone reveals the full surface.  
   * *Access Lockout:* SSH shells and system root are locked, preventing traditional white-box inspection.  
   * *The Execution Gap:* Naive protocol fuzzing fails because transport-layer acknowledgments (e.g., rosbridge JSON ACK) occur downstream of safety gates (e.g., control\_state \== 30), leading to ignored commands.  
       
2. **State the Scientific Contributions explicitly (C1–C7):**  
   * **C1:** The generalizable 7-phase non-destructive protocol reconstruction pipeline.  
   * **C2:** Reconstructed command and telemetry schema for closed dual-IP Android-ROS architectures.  
   * **C3:** An edge-first 3-layer software stack (Presentation, Application, Domain) operating independently of cloud backends.  
   * **C4:** TTS channel discovery via Android IPC (am broadcast) to native speech engines.  
   * **C5:** Interaction layer with cloud-independent, offline conversational primitives (phonetic STT tuning and CASIA/VGGFace2 FaceNet re-ID).  
   * **C6:** A field-driven reactivity optimization (*State Short-Circuiting*) that reduces Wi-Fi bottlenecking.  
   * **C7:** Empirical validation and reverse-engineering labor metrics on a physical mobile platform.

### **Step 3: Formalizing Hypotheses (H1–H4) & The Methodology**

Instruct your student to structure Section III of the paper strictly around hypotheses and empirical falsification:

* **H1 (APK-as-Spec):** Vendor APK static analysis (JADX) yields the actual wire-protocol schemas used by the chassis.  
  * *Verdict:* **Confirmed.** Static analysis of welcomepatrol and sentrymove identified 455 topics and 308 services verified on the wire.  
* **H2 (MQTT-as-Command):** The exposed MQTT broker (port 1883\) can be used to issue motion commands in parallel to ROSBRIDGE.  
  * *Verdict:* **Rejected.** Passive auditing proved MQTT is an asynchronous, read-only telemetry mirror for cloud dashboards.  
* **H3 (POI Reuse):** Reusing vendor Deployment Tool Points of Interest (POIs) via /tag\_manager/navi yields higher navigation reliability than independently derived coordinates on /navi\_goal.  
  * *Verdict:* **Confirmed (Conditional).** Bypasses frame drift by leveraging the internal marker\_manager, given localization confidence $\>60\\%$ and automatic mode active.  
* **H4 (Transport $\\neq$ Execution):** A ROSBRIDGE transport acknowledgment does not guarantee chassis execution.  
  * *Verdict:* **Confirmed.** Ground-truth execution must be inferred by monitoring pose deltas (/robot\_pose) and status codes (nav\_status \== 602 \\rightarrow 603).

**Methods Table to Include (7-Phase Pipeline):**

* *Phase 1:* Network Scan (Dual-IP mapping: 10.42.0.1 AP, 192.168.20.x eth0 bridge).  
* *Phase 2:* ROS Introspection via rosapi over WebSocket (port 9090).  
* *Phase 3:* MQTT Passive Observation.  
* *Phase 4:* APK Audit (JADX decompilation for hidden service parameters).  
* *Phase 5:* Wireshark Frame Inspection.  
* *Phase 6:* ADB/Termux Edge Integration (TTS bridge and Starlette backend).  
* *Phase 7:* Empirical Field Validation.


### **Step 4: System Architecture & Technical Nuances**

Guide your student to highlight technical innovations that overcome hardware constraints:

1. **Network Topology & Dual-IP Architecture:** Detail the eth0 bridge (192.168.20.1 head to 192.168.20.22 chassis) vs. DHCP Wi-Fi segments (172.16.0.x), identifying head-chassis IP conflation as the leading operator error during deployment.  
2. **The Termux Python 3.13 Constraint:** Explain the architectural pivot from FastAPI to Starlette for the on-device Lite backend (cybel\_lite.py) due to compilation failures of pydantic-core on Python 3.13 inside Android's Termux environment.  
3. **Android TTS IPC Bridge:** Detail the CybelTTSBridge native Java app using an Android BroadcastReceiver listening to com.cybel.ttsbridge.SPEAK to trigger speech when ROS offers no audio interface.

### **Step 5: Field Results, Performance Indicators, and Optimizations**

Ensure the paper relies on quantitative evaluation tables:

1. **Reactivity Optimization (C6):** Explain how suppressing redundant /change\_location\_mode calls when telemetry already confirms control\_state \== 30 eliminated two ROSBRIDGE round-trips per waypoint, resolving navigation sluggishness.  
2. **Navigation Reliability Metrics:** Contrast coordinate-only /navi\_goal (susceptible to stalling at status code 601 without transitioning to 602) vs. POI-based marker management (/tag\_manager/navi), which achieved a 100% tour completion rate across all trials.  
3. **System Performance Benchmarks:**  
   * Local API Latency: \<100 ms.  
   * ROSBRIDGE Session Reliability: approx 90 %.  
   * Guided-tour Success: 100% (3/3 trials).  
   * TTS Bridge Latency: Mean 923 ms 651--1555ms across 5 trials).  
     

### **Step 6: Ethical Principles & Generalization Discussion**

* **Ethical Data Provenance:** Highlight that local face re-identification models were trained on CASIA-WebFace and VGGFace2, explicitly excluding the ethically retracted MS-Celeb-1M dataset.  
* **Non-Destructive Principle (P4):** State that all protocol discovery preserves warranty seals, uses non-invasive interfaces (rosbridge, ADB, public broadcasts), and processes all biometrics purely on the edge (transmitting vector embeddings, never raw images).  
* **Generalizability:** Discuss how the H1–H4 framework and 7-phase pipeline apply directly to other closed mobile platforms running dual Android-ROS stacks (e.g., Temi, Pepper, Keenon).

