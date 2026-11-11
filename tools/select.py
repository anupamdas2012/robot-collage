#!/usr/bin/env python3
"""Filter the raw search pool (items.jsonl) down to genuine robotics projects.

Many repos tag `robotics` among a dozen unrelated topics (CS course lists, ML
megarepos). We keep a repo only when robotics is clearly core: a strong robotics
topic, or a strong robotics signal in the name/description. Generic CS/ML meta
lists are dropped. Output: top-N by stars -> .context/raw/repos.json

Run:  python3 -I tools/select.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".context" / "raw"
CAP = 300

STRONG = {
    "ros","ros2","ros-noetic","ros2-humble","ros-melodic","ros-foxy","robot-operating-system",
    "rclcpp","rclpy","micro-ros","ros-industrial",
    "slam","visual-slam","lidar-slam","vslam","visual-odometry","lidar-odometry",
    "visual-inertial-odometry","vio","lidar","pointcloud-registration","loop-closure",
    "drone","uav","uas","quadcopter","multirotor","px4","ardupilot","mavlink","betaflight",
    "fpv","crazyflie","aerial-robotics","drones",
    "humanoid","humanoid-robot","quadruped","quadruped-robot","legged-robots","legged",
    "legged-robot","biped","bipedal","hexapod","legged-locomotion",
    "robot-arm","robotic-arm","manipulation","manipulator","grasping","grasp","moveit",
    "end-effector","dexterous","dexterous-manipulation","robotic-manipulation",
    "motion-planning","path-planning","trajectory-optimization","nav2","navigation2",
    "forward-kinematics","inverse-kinematics","kinematics","urdf",
    "gazebo","mujoco","pybullet","isaac-sim","isaac-gym","isaacgym","webots",
    "robotics-simulation","robot-simulator","robot-simulation","bullet-physics",
    "autonomous-driving","self-driving","self-driving-car","autonomous-vehicles",
    "autonomous-vehicle","autonomous-robots","autonomous-navigation","autoware","carla",
    "mobile-robot","mobile-robots","turtlebot","differential-drive","wheeled-robot",
    "robot-learning","embodied-ai","embodied-agent","sim-to-real","robot-control",
    "robotics-control","locomotion","whole-body-control","model-predictive-control",
    "teleoperation","ros-robot","robotics-algorithms","swarm-robotics","ros2-humble",
    "collision-avoidance","obstacle-avoidance","state-estimation","sensor-fusion",
    "quadrotor","rover","underwater-robotics","agv","amr",
}
WEAK = {"robotics","robots","mechatronics","robotic"}
# "bot"/"automation" are NOT physical-robotics signals on their own: chat bots, RPA,
# web scrapers and GUI automation hijack them. Any ANTI topic with no STRONG topic -> drop.
ANTI = {
    "chatbot","chatbots","chat-bot","chat","wechat","weixin","qqbot","mirai","rpa",
    "robotic-process-automation","web-scraping","scraping","scraper","crawler","spider",
    "web-crawler","desktop-automation","gui-automation","browser-automation",
    "automation-testing","test-automation","testing","selenium","appium","playwright",
    "discord","discord-bot","telegram","telegram-bot","slack","slack-bot","whatsapp",
    "trading-bot","twitter-bot","instagram-bot","game-bot","workflow-automation",
    "task-automation","home-assistant","devops","ci-cd","web","frontend-framework",
}
BROAD_OFFTOPIC = {
    "machine-learning","deep-learning","computer-vision","data-science","web-development",
    "algorithms","security","blockchain","nlp","natural-language-processing",
    "artificial-intelligence","tensorflow","pytorch","keras","neural-network","llm",
    "gpt","chatgpt","stable-diffusion","data-structures","leetcode","interview-questions",
    "frontend","backend","operating-system","computer-architecture","database","databases",
    "image-processing","object-detection","data-analysis","statistics","mathematics",
    "programming","python","cpp","javascript","java","awesome-list","roadmap",
}
META_RE = re.compile(r"\b(awesome|roadmap|curriculum|tutorials?|cheat[-\s]?sheet|interview|"
                     r"books?|lectures?|courses?|resources|reading[-\s]?list|paper[-\s]?list|"
                     r"100[-\s]?days|zero[-\s]?to|bootcamp|syllabus|handbook|collection of|"
                     r"list of|free-programming|study-guide|notes)\b", re.I)
DESC_STRONG_RE = re.compile(
    r"(\bros ?2?\b|\bslam\b|\buav\b|\bugv\b|\bdrone|quadruped|quadcopter|humanoid|bipedal|"
    r"hexapod|\bmanipulat|robot(ic)? arm|\bmoveit\b|gazebo|mujoco|pybullet|teleoperation|"
    r"legged robot|self[- ]driving|autonomous (driving|vehicle|navigation|robot|car|mobile)|"
    r"\bquadrotor\b|\blidar\b|motion planning|path planning|forward kinematics|"
    r"inverse kinematics|reinforcement learning.{0,20}robot|robot.{0,20}reinforcement)", re.I)
DENY_NAMES = {
    "developer-y/cs-video-courses","josephmisiti/awesome-machine-learning",
    "chandlerbing65nm/awesome-deep-learning","floodsung/deep-learning-papers-reading-roadmap",
    "d2l-ai/d2l-en","tensorflow/tensorflow","pytorch/pytorch","keras-team/keras",
    "opencv/opencv","scikit-learn/scikit-learn",
    # chat/RPA/web-automation bots and non-robotics megarepos that slipped through
    "naibowang/easyspider","littlecodersh/itchat","wechaty/wechaty","hubotio/hubot",
    "go-vgo/robotgo","questdb/questdb","earthtojake/text-to-cad",
    "harvard-edge/cs249r_book","tianxingchen/embodied-ai-guide","ewenwan/mvision",
    "paddlepaddle/paddleseg","cirosantilli/china-dictatorship",
}

def is_robotics(r):
    fn = r["full_name"].lower()
    if fn in DENY_NAMES:
        return False
    topics = set(t.lower() for t in (r.get("topics") or []))
    name = r["name"].lower()
    # Guard against keyword-stuffed / troll descriptions: only trust the opening.
    desc = (r.get("description") or "")[:400]
    hay = name + " " + desc.lower()
    strong = bool(topics & STRONG)
    desc_strong = bool(DESC_STRONG_RE.search(hay))
    weak = bool(topics & WEAK) or ("robot" in name)
    meta = bool(META_RE.search(hay))
    offtopic = len(topics & BROAD_OFFTOPIC)

    # chat bot / RPA / web-automation / test-automation masquerading as "robot"
    if (topics & ANTI) and not strong:
        return False

    if strong:
        # a strong robotics topic wins, unless it's plainly a generic meta megalist
        if meta and "robot" not in name and offtopic >= 3:
            return False
        return True
    if desc_strong:
        if meta and "robot" not in name and offtopic >= 3:
            return False
        return True
    if weak:
        # only weak 'robot(ics)' signal -> must not look like a generic CS/ML list
        if meta and "robot" not in name:
            return False
        if offtopic >= 2:
            return False
        return True
    return False

def main():
    items = {}
    kept = dropped = 0
    with (RAW / "items.jsonl").open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("stars") is None or r.get("archived") is True:
                continue
            if not is_robotics(r):
                dropped += 1
                continue
            kept += 1
            fn = r["full_name"]
            if fn not in items or r["stars"] > items[fn]["stars"]:
                items[fn] = r
    repos = sorted(items.values(), key=lambda x: -x["stars"])[:CAP]
    (RAW / "repos.json").write_text(json.dumps(repos, indent=1))
    print(f"pool rows: kept={kept} dropped={dropped} | unique robotics={len(items)} | capped={len(repos)}")
    print("min stars in final set:", repos[-1]["stars"])
    print("\nTop 30 after filtering:")
    for r in repos[:30]:
        print(f"  {r['stars']:>7}  {r['full_name']}")

if __name__ == "__main__":
    main()
