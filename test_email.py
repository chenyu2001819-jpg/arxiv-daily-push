#!/usr/bin/env python3
"""
arXiv Agent 邮件配置测试工具
"""

import os
import sys
import yaml

print("=" * 60)
print("📧 arXiv Agent 邮件配置测试工具")
print("=" * 60)
print()

# 检查配置文件
if not os.path.exists("config.yaml"):
    print("❌ 未找到 config.yaml 文件！")
    print("请确保你在正确的目录中运行此脚本。")
    sys.exit(1)

# 加载配置
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

email_config = config.get("email", {})

print("当前邮件配置：")
print(f"  启用状态: {'✅ 已启用' if email_config.get('enabled') else '❌ 未启用'}")
print(f"  发件人: {email_config.get('sender_email', '未设置')}")
print(f"  收件人: {', '.join(email_config.get('receiver_emails', ['未设置']))}")
print(f"  SMTP服务器: {email_config.get('smtp_host', '自动检测')}")
print(f"  SMTP端口: {email_config.get('smtp_port', '自动检测')}")
print()

if not email_config.get('enabled'):
    print("⚠️ 邮件功能未启用！")
    print("请编辑 config.yaml，将 email.enabled 设置为 true")
    print()
    print("配置示例：")
    print("  email:")
    print("    enabled: true")
    print("    sender_email: \"your_email@qq.com\"")
    print("    sender_password: \"your_auth_code\"")
    print("    receiver_emails:")
    print("      - \"receiver@example.com\"")
    sys.exit(1)

if email_config.get('sender_email') == 'your_email@example.com':
    print("⚠️ 请修改 config.yaml 中的邮箱配置！")
    print("当前使用的是默认占位符邮箱。")
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
    sys.exit(1)
