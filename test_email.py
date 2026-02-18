#!/usr/bin/env python3
"""
arXiv Agent 邮件配置测试工具
"""

import os
import sys

print("=" * 60)
print("📧 arXiv Agent 邮件配置测试工具")
print("=" * 60)
print()

# 从环境变量读取配置（GitHub Actions）
email_enabled = os.environ.get('EMAIL_ENABLED', '').lower()
sender_email = os.environ.get('EMAIL_SENDER', '')
sender_password = os.environ.get('EMAIL_PASSWORD', '')
receivers_str = os.environ.get('EMAIL_RECEIVERS', '')

print("当前邮件配置：")
print(f"  启用状态: {'✅ 已启用' if email_enabled in ('true', '1', 'yes') else '❌ 未启用'}")
print(f"  发件人: {sender_email if sender_email else '未设置'}")
print(f"  收件人: {receivers_str if receivers_str else '未设置'}")
print()

if email_enabled not in ('true', '1', 'yes'):
    print("⚠️ 邮件功能未启用！")
    print("请设置 Secrets EMAIL_ENABLED=true")
    sys.exit(1)

if not sender_email or sender_email == 'your_email@example.com':
    print("⚠️ 请配置发件人邮箱！")
    print("请设置 Secrets EMAIL_SENDER")
    sys.exit(1)

if not sender_password:
    print("⚠️ 请配置邮箱密码/授权码！")
    print("请设置 Secrets EMAIL_PASSWORD")
    sys.exit(1)

if not receivers_str:
    print("⚠️ 请配置收件人邮箱！")
    print("请设置 Secrets EMAIL_RECEIVERS")
    sys.exit(1)

# 构建配置
email_config = {
    'enabled': True,
    'sender_email': sender_email,
    'sender_password': sender_password,
    'receiver_emails': [e.strip() for e in receivers_str.split(',') if e.strip()],
    'smtp_host': os.environ.get('SMTP_HOST', ''),
    'smtp_port': int(os.environ.get('SMTP_PORT', '465') or '465'),
    'use_ssl': os.environ.get('USE_SSL', 'true').lower() == 'true',
    'use_tls': os.environ.get('USE_TLS', 'false').lower() == 'true',
}

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
        
        # 发送测试邮件
        print("正在发送测试邮件...")
        
        from dataclasses import dataclass, field
        from datetime import datetime
        from typing import List
        
        @dataclass
        class TestPaper:
            title: str
            authors: List[str]
            summary: str
            link: str
            pdf_link: str
            published: datetime
            categories: List[str]
            primary_category: str
            arxiv_id: str = ""
            citation_count: int = 0
            matched_keywords: List[str] = field(default_factory=list)
            source_block: str = "测试"
            keyword_type: str = "core"
        
        test_papers = [
            TestPaper(
                title="Test Email - arXiv Daily Push Configuration",
                authors=["arXiv Agent"],
                summary="This is a test email to verify that your email configuration is working correctly.",
                link="https://arxiv.org",
                pdf_link="https://arxiv.org",
                published=datetime.now(),
                categories=["test"],
                primary_category="test",
                citation_count=42
            )
        ]
        
        email_sent = sender.send_papers_email(
            test_papers,
            "",
            datetime.now().strftime('%Y-%m-%d')
        )
        
        if email_sent:
            print()
            print("📧 测试邮件已发送！")
            print(f"请检查收件箱: {', '.join(email_config['receiver_emails'])}")
        else:
            print()
            print("⚠️ 测试邮件发送失败")
            
        print()
        print("你现在可以运行正式任务了！")
        
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
