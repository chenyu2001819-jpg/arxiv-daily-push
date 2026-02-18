#!/usr/bin/env python3
"""
arXiv Agent 定时任务调度器
支持每天定时运行、后台运行、日志记录、邮件推送
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from arxiv_agent import ArxivAgent

# 配置日志
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(log_dir, f"scheduler_{datetime.now().strftime('%Y%m')}.log"),
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


def job():
    """定时执行的任务"""
    logger.info("=" * 60)
    logger.info("开始执行定时任务")
    logger.info("=" * 60)
    
    try:
        agent = ArxivAgent()
        report_path = agent.run(send_email=True)
        logger.info(f"✅ 任务完成，报告: {report_path}")
        
        # 检查邮件是否发送成功
        if agent.email_sender:
            receivers = agent.config.get('email', {}).get('receiver_emails', [])
            logger.info(f"📧 邮件已发送至: {', '.join(receivers)}")
        
    except Exception as e:
        logger.exception(f"❌ 任务执行失败: {e}")


def run_scheduler(time_str: str = "09:00"):
    """
    启动定时调度器
    
    Args:
        time_str: 每天运行时间，格式 "HH:MM"
    """
    logger.info(f"🚀 启动定时调度器，每天 {time_str} 执行")
    
    # 设置定时任务
    schedule.every().day.at(time_str).do(job)
    
    # 立即执行一次（可选）
    # job()
    
    logger.info("按 Ctrl+C 停止调度器")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def run_once():
    """立即执行一次"""
    job()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='arXiv Agent 调度器')
    parser.add_argument(
        '--run-once', 
        action='store_true',
        help='立即执行一次，不启动定时调度'
    )
    parser.add_argument(
        '--time',
        default='09:00',
        help='定时执行时间 (默认: 09:00)'
    )
    parser.add_argument(
        '--test-email',
        action='store_true',
        help='测试邮件配置'
    )
    
    args = parser.parse_args()
    
    if args.test_email:
        agent = ArxivAgent()
        success = agent.test_email()
        exit(0 if success else 1)
    
    if args.run_once:
        run_once()
    else:
        run_scheduler(args.time)
