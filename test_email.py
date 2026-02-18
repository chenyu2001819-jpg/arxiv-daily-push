#!/usr/bin/env python3
"""
arXiv Agent 邮件配置测试工具
支持从 config.yaml 或环境变量读取配置（GitHub Actions）
"""

import os
import sys
import yaml

print("=" * 60)
print("📧 arXiv Agent 邮件配置测试工具")
print("=" * 60)
print()


def load_config_from_env():
    """从环境变量加载配置（用于 GitHub Actions）"""
    config = {}
    
    email_enabled = os.environ.get('EMAIL_ENABLED', '').lower()
    if email_enabled in ('true', '1', 'yes'):
        config['email'] = {
            'enabled': True,
            'sender_email': os.environ.get('EMAIL_SENDER', ''),
            'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
            'receiver_emails': os.environ.get('EMAIL_RECEIVERS', '').split(','),
            'smtp_host': os.environ.get('SMTP_HOST', ''),
            'smtp_port': int(os.environ.get('SMTP_PORT', '465') or '465'),
            'use_ssl': os.environ.get('USE_SSL', 'true').lower() == 'true',
            'use_tls': os.environ.get('USE_TLS', 'false').lower() == 'true',
        }
        # 清理空的收件人
        config['email']['receiver_emails'] = [
            email.strip() for email in config['email']['receiver_emails'] 
            if email.strip()
        ]
    
    return config


def load_config_from_file():
    """从配置文件加载"""
    if not os.path.exists("config.yaml"):
        return None
    
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# 优先从环境变量加载（GitHub Actions），其次从配置文件加载
config = load_config_from_env()

if not config:
    config = load_config_from_file()
    if not config:
        print("❌ 未找到配置文件或环境变量！")
        print()
        print("本地运行：请创建 config.yaml 文件")
        print("GitHub Actions：请检查 Secrets 是否已配置")
        sys.exit(1)

email_config = config.get("email", {})

print("当前邮件配置：")
print(f"  启用状态: {'✅ 已启用' if email_config.get('enabled') else '❌ 未启用'}")
print(f"  发件人: {email_config.get('sender_email', '未设置')}")

receivers = email_config.get('receiver_emails', [])
if receivers:
    print(f"  收件人: {', '.join(receivers)}")
else:
    print(f"  收件人: 未设置")

print(f"  SMTP服务器: {email_config.get('smtp_host', '自动检测')}")
print(f"  SMTP端口: {email_config.get('smtp_port', '自动检测')}")
print()

if not email_config.get('enabled'):
    print("⚠️ 邮件功能未启用！")
    print()
    print("本地运行：请编辑 config.yaml，将 email.enabled 设置为 true")
    print("GitHub Actions：请设置 Secrets EMAIL_ENABLED=true")
    print()
    print("配置示例：")
    print("  email:")
    print("    enabled: true")
    print("    sender_email: \"your_email@qq.com\"")
    print("    sender_password: \"your_auth_code\"")
    print("    receiver_emails:")
    print("      - \"receiver@example.com\"")
    print()
    print("当前环境变量：")
    print(f"  EMAIL_ENABLED={os.environ.get('EMAIL_ENABLED', '未设置')}")
    print(f"  EMAIL_SENDER={os.environ.get('EMAIL_SENDER', '未设置')}")
    print(f"  EMAIL_PASSWORD={'已设置' if os.environ.get('EMAIL_PASSWORD') else '未设置'}")
    print(f"  EMAIL_RECEIVERS={os.environ.get('EMAIL_RECEIVERS', '未设置')}")
    sys.exit(1)

if email_config.get('sender_email') in ('your_email@example.com', '', None):
    print("⚠️ 请配置发件人邮箱！")
    print("本地运行：修改 config.yaml 中的 sender_email")
    print("GitHub Actions：设置 Secrets EMAIL_SENDER")
    sys.exit(1)

if not email_config.get('sender_password'):
    print("⚠️ 请配置邮箱密码/授权码！")
    print("本地运行：修改 config.yaml 中的 sender_password")
    print("GitHub Actions：设置 Secrets EMAIL_PASSWORD")
    sys.exit(1)

if not email_config.get('receiver_emails'):
    print("⚠️ 请配置收件人邮箱！")
    print("本地运行：修改 config.yaml 中的 receiver_emails")
    print("GitHub Actions：设置 Secrets EMAIL_RECEIVERS")
    sys.exit(1)

# 测试连接
print("正在测试邮件服务器连接...")
print()

try:
    from email_sender import EmailSender
    
    sender = EmailSender(email_config)
    success = sender.test_connection()
    
    if success:
        print()
        print("=" * 60)
        print("✅ 邮件配置测试通过！")
        print("=" * 60)
        print()
        print("你现在可以运行以下命令开始推送：")
        print("  python arxiv_agent.py")
        print()
    else:
        print()
        print("=" * 60)
        print("❌ 邮件配置测试失败！")
        print("=" * 60)
        print()
        print("常见问题：")
        print("  1. QQ邮箱/163邮箱需要填写授权码，不是登录密码")
        print("  2. 检查邮箱是否开启了 SMTP 服务")
        print("  3. 检查网络连接是否正常")
        print("  4. 如果使用公司网络，检查是否屏蔽了 SMTP 端口")
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保已安装依赖: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
