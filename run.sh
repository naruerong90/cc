#!/bin/bash
# run.sh - สคริปต์เริ่มการทำงานของระบบนับลูกค้า

# ไม่บัฟเฟอร์ stdout และ stderr
export PYTHONUNBUFFERED=1

# คำสั่งเริ่มการทำงาน
python main.py $@
