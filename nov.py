import os
import re
from datetime import datetime
from uagents import Agent, Context, Model, Protocol
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

# ===== Models for ASI:One chat =====
class ChatMessage(Model):
    timestamp: str  # ISO format string for JSON compatibility
    msg_id: str
    content: list   # List of text/content items

class ChatConfirmation(Model):
    timestamp: str  # ISO format string for JSON compatibility
    msg_id: str

class ChatPing(Model):
    timestamp: str  # ISO format string for JSON compatibility

# ===== Create Agent =====
agent = Agent(
    name="Study Buddy",
    seed=os.getenv("AGENT_SEED_PHRASE", "study_buddy_unique_seed_2026"),
    port=8008,
    endpoint=["http://localhost:8008/submit"],
)

# ===== Create Protocol =====
chat_proto = Protocol(
    name="AgentChatProtocol",
    version="0.1.0"
)

# ===== Helper Functions =====
def build_plan(subject: str, exam_date: str) -> str:
    try:
        exam = datetime.strptime(exam_date, "%d/%m/%Y")
        days_left = (exam - datetime.now()).days
    except ValueError:
        days_left = 7  # Fallback duration

    days_left = max(days_left, 1)
    topics = [
        "Basics & fundamentals", "Core concepts", "Practice problems",
        "Advanced topics", "Revision + weak areas", "Mock test", "Final revision"
    ]

    plan = [f"📚 Study Plan for {subject}", f"🗓 Exam in {days_left} days", ""]
    per_day = topics if days_left >= len(topics) else topics[:days_left]
    for i, topic in enumerate(per_day, 1):
        plan.append(f"Day {i}: {topic} in {subject} (2-3 hrs)")
    plan.append("")
    plan.append("💪 Consistency beats cramming. Good luck!")
    return "\n".join(plan)

def parse_request(text: str):
    # Parse date formatted like 20/11/2026 or 20-11-2026
    m = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
    date = m.group(1).replace("-", "/") if m else None
    
    # Parse subject name following "for"
    subj = re.search(r"for ([A-Za-z0-9+# .]+?)(?: on| exam|\d|$)", text, re.IGNORECASE)
    subject = subj.group(1).strip() if subj else None
    return subject, date

# ===== Protocol Message Handlers =====
@chat_proto.on_message(model=ChatPing)
async def handle_ping(ctx: Context, sender: str, msg: ChatPing):
    ctx.logger.info(f"Ping received from {sender}")

@chat_proto.on_message(model=ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Message received from {sender}")

    # Extract text from message content
    user_text = ""
    for item in msg.content:
        if isinstance(item, dict) and item.get("type") == "text":
            user_text += item.get("text", "")

    # Send confirmation acknowledgment back
    await ctx.send(sender, ChatConfirmation(
        timestamp=datetime.now().isoformat(),
        msg_id=msg.msg_id
    ))

    subject, date = parse_request(user_text)

    if subject:
        reply = build_plan(subject, date or "01/01/2030")
    else:
        reply = (
            "Hi! I'm Study Buddy 📚\n\n"
            "Tell me your subject and exam date and I'll build you a study plan!\n\n"
            "Example: 'Make a plan for DBMS exam on 20/11/2026'"
        )

    # Reply with constructed response
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now().isoformat(),
        msg_id=str(agent.address),
        content=[{"type": "text", "text": reply}]
    ))

# Include protocol in agent and publish its manifest to Agentverse
agent.include(chat_proto, publish_manifest=True)

# ===== Startup Handler =====
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("Study Buddy is active and running!")

    api_key = os.getenv("AGENTVERSE_KEY", "")

    if api_key:
        try:
            register_chat_agent(
                "studypoint",
                f"https://agentverse.ai/inspect/?uri=http%3A%2F%2F127.0.0.1%3A8003&address={agent.address}",
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=api_key,
                    agent_seed_phrase=os.getenv("AGENT_SEED_PHRASE", "study_buddy_unique_seed_2026"),
                ),
            )
            ctx.logger.info("Chat agent successfully registered on Agentverse!")
        except Exception as e:
            ctx.logger.error(f"Registration failed: {e}")
    else:
        ctx.logger.warning("AGENTVERSE_KEY not set. Running in local mode without Agentverse registration.")

if __name__ == "__main__":
    agent.run()