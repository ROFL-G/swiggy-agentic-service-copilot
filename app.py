import os
import sys
import socket
import gradio as gr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ==============================================================================
# 1. ENTERPRISE KNOWLEDGE BASE (DOMAIN RAG)
# Standard Operating Procedures across Food Delivery, Instamart, and Dineout
# ==============================================================================
SWIGGY_KNOWLEDGE_BASE = [
    {
        "clause_id": "SWG-FOOD-101",
        "category": "Missing Item & Kitchen Omission",
        "content": (
            "SOP SWG-FOOD-101: Food Delivery Missing Item Protocol. If a consumer reports a missing "
            "dish from a sealed restaurant package and the merchant KPT (Kitchen Preparation Time) "
            "log does not disprove the omission, issue an instant prorated refund to Swiggy Money Wallet "
            "for the missing item value plus taxes. Do not penalize the delivery partner if the tamper-evident "
            "bag seal was intact upon handover."
        )
    },
    {
        "clause_id": "SWG-INSTA-204",
        "category": "Quick-Commerce Cold-Chain & Perishable Damage",
        "content": (
            "SOP SWG-INSTA-204: Instamart Damaged / Leaking Perishables. For cold-chain dairy, milk pouches, "
            "or fresh produce delivered leaking or damaged, verify uploaded photo proof. If the consumer holds "
            "an active Swiggy One membership and Concession Abuse Score (CAS) is below 0.35, offer an immediate "
            "10-minute priority dark store replacement dispatch. If out of stock, grant an instant full refund."
        )
    },
    {
        "clause_id": "SWG-FLEET-302",
        "category": "Delivery Telemetry & False Delivery Scan",
        "content": (
            "SOP SWG-FLEET-302: Geofence Discrepancy & Premature Order Completion. When a delivery partner marks "
            "an order as 'Delivered' while real-time GPS telemetry indicates the ping was >150 meters away "
            "from customer doorstep coordinates, flag as premature drop. Trigger an automated IVR bridge to the "
            "delivery partner and hold customer payout deduction pending physical location re-verification."
        )
    },
    {
        "clause_id": "SWG-RISK-405",
        "category": "Concession Abuse & Fraud Velocity Lock",
        "content": (
            "SOP SWG-RISK-405: Concession Abuse Score (CAS) Thresholds. If an account has a CAS > 0.70 "
            "or has initiated >3 refund claims in the last 7 calendar days, block automated wallet payouts. "
            "Require mandatory manual Tier-2 supervisor sign-off and secondary photo inspection of the item barcode."
        )
    },
    {
        "clause_id": "SWG-DINE-501",
        "category": "Dineout Bill Payment & Discount Discrepancy",
        "content": (
            "SOP SWG-DINE-501: Dineout Instant Discount Settlement. When a diner's bank card offer is rejected "
            "at restaurant POS checkout via Swiggy Dineout Pay, verify gateway payment status. If debited without "
            "discount applied, issue an instant credit note of the delta value to Swiggy Money within 15 minutes."
        )
    },
    {
        "clause_id": "SWG-SAFE-601",
        "category": "Severe Contamination & Food Safety Alert",
        "content": (
            "SOP SWG-SAFE-601: Food Contamination & Allergen Violation. For foreign objects, rancid food, or "
            "critical allergen omissions, immediately initiate a 100% full order refund regardless of CAS tier, "
            "place an automated 2-hour onboarding hold on the merchant kitchen, and flag for Food Safety Audit."
        )
    }
]

# In-memory TF-IDF Vector RAG (<25 MB RAM footprint)
docs = [item["content"] for item in SWIGGY_KNOWLEDGE_BASE]
vectorizer = TfidfVectorizer().fit(docs)
doc_vectors = vectorizer.transform(docs)

def query_swiggy_rag(query_text: str) -> dict:
    """Retrieves grounded Swiggy SOP clauses based on cosine semantic similarity."""
    query_vec = vectorizer.transform([query_text])
    similarities = cosine_similarity(query_vec, doc_vectors)[0]
    best_match_idx = int(similarities.argmax())
    return SWIGGY_KNOWLEDGE_BASE[best_match_idx]

# ==============================================================================
# 2. PRE-CONFIGURED INCIDENTS & MOCK DATA
# ==============================================================================
MOCK_SWIGGY_TICKETS = {
    "SWG-ORD-9102 (Missing Restaurant Item)": {
        "customer": "Rohan Mehta",
        "user_id": "usr-delhi-8812",
        "order_id": "OD-FOOD-99120",
        "vertical": "Food Delivery",
        "membership": True,
        "merchant": "Meghana Foods (Koramangala)",
        "items": "1x Special Chicken Biryani, 1x Paneer Tikka (₹780 total)",
        "default_query": "The tamper-evident tape is intact, but the restaurant failed to pack the Paneer Tikka dish!",
        "cas_score": 0.12
    },
    "SWG-ORD-4419 (Instamart Damaged Perishable)": {
        "customer": "Priya Sharma",
        "user_id": "usr-blr-4402",
        "order_id": "OD-INSTA-30192",
        "vertical": "Instamart Quick-Commerce",
        "membership": True,
        "merchant": "Instamart Pod #14 (Indiranagar)",
        "items": "2x Nandini GoodLife Milk 1L, 1x Sourdough Loaf (₹210 total)",
        "default_query": "My milk pouch was punctured and leaking all over the sourdough bread. Completely unusable packaging!",
        "cas_score": 0.22
    },
    "SWG-ORD-7721 (Rider False Delivery Geofence)": {
        "customer": "Amitabh Roy",
        "user_id": "usr-mum-1094",
        "order_id": "OD-FOOD-55102",
        "vertical": "Food Delivery",
        "membership": False,
        "merchant": "Social (Powai)",
        "items": "1x Butter Chicken, 2x Garlic Naan (₹620 total)",
        "default_query": "Order is marked 'Delivered' on the app, but no delivery partner ever reached my gate or called me.",
        "cas_score": 0.18
    },
    "SWG-ORD-1105 (High Risk Fraud Flag)": {
        "customer": "Vikram Das",
        "user_id": "usr-hyd-3301",
        "order_id": "OD-INSTA-88210",
        "vertical": "Instamart Quick-Commerce",
        "membership": False,
        "merchant": "Instamart Pod #07 (Hitec City)",
        "items": "1x Ferrero Rocher 24pc Box (₹950 total)",
        "default_query": "The chocolate box is dented on the corner. Give me my full cash refund right now without any delay.",
        "cas_score": 0.84
    },
    "SWG-ORD-6230 (Dineout Gateway Error)": {
        "customer": "Neha Kapoor",
        "user_id": "usr-del-7120",
        "order_id": "OD-DINE-44019",
        "vertical": "Dineout",
        "membership": True,
        "merchant": "Farzi Cafe (CyberHub)",
        "items": "Dine-in bill ₹4,200",
        "default_query": "Paid via Dineout Pay with HDFC card offer, but the 15% discount was not credited on the final debited amount.",
        "cas_score": 0.10
    }
}

# ==============================================================================
# 3. MOCK HYPERLOCAL AGENT TOOLS
# ==============================================================================
def tool_query_fleet_telemetry(order_id: str, query_text: str) -> dict:
    """Tool: Validates rider GPS coordinates against customer doorstep geofence."""
    if "marked" in query_text.lower() or "delivered" in query_text.lower() or "55102" in order_id:
        return {
            "order_id": order_id,
            "rider_id": "DE-MUM-4029",
            "distance_from_doorstep_meters": 420,
            "geofence_status": "BREACH_PREMATURE_DROP",
            "speed_kmph": 24.5
        }
    return {
        "order_id": order_id,
        "rider_id": "DE-BLR-1102",
        "distance_from_doorstep_meters": 28,
        "geofence_status": "VERIFIED_AT_DOORSTEP",
        "speed_kmph": 0.0
    }

def tool_inspect_fulfillment_source(order_id: str, vertical: str) -> dict:
    """Tool: Audits dark store WMS barcode scans or restaurant kitchen prep telemetry."""
    if "Instamart" in vertical or "INSTA" in order_id:
        return {
            "facility_type": "Instamart Dark Store Pod",
            "wms_bin_status": "CONFIRMED_PICKED_ALL_SKUS",
            "cold_chain_packaging": "Standard Polybag (Unpadded)"
        }
    return {
        "facility_type": "Restaurant Kitchen",
        "kpt_duration_minutes": 15.4,
        "tamper_tape_applied": True,
        "dispatch_bag_count": 1
    }

def tool_execute_order_remediation(action_type: str, target_id: str) -> str:
    """Tool: Programmatically executes wallet concessions, re-orders, or escalations."""
    if action_type == "INSTANT_WALLET_REFUND":
        return f"SUCCESS: Refund of ₹310.00 credited to Swiggy Money for '{target_id}' (Ref: SWG-RFND-9941)."
    elif action_type == "DISPATCH_INSTAMART_REPLACEMENT":
        return f"SUCCESS: Priority 10-Minute replacement order #OD-INSTA-REP-1101 dispatched from nearest pod for '{target_id}'."
    elif action_type == "TRIGGER_RIDER_IVR_BRIDGE":
        return f"SUCCESS: Outbound IVR call initiated to delivery partner for '{target_id}'. Doorstep re-routing active."
    elif action_type == "BLOCK_AND_ESCALATE_TIER2":
        return f"HOLD: High CAS risk detected. Automated payout blocked for '{target_id}'. Ticket routed to Senior CSA."
    elif action_type == "FOOD_SAFETY_EMERGENCY":
        return f"CRITICAL: 100% full refund issued. Automated 2-hour kitchen dispatch hold applied for merchant investigation."
    return "STATUS: Standard ticket routing logged."

# ==============================================================================
# 4. AUTONOMOUS REACT AGENT WORKFLOW
# ==============================================================================
def run_swiggy_copilot(
    ticket_selection: str,
    custom_query: str,
    override_cas: float,
    swiggy_one_status: bool,
    vertical_selection: str
) -> tuple[str, str, str]:
    ticket = MOCK_SWIGGY_TICKETS.get(ticket_selection, {})
    
    user_name = ticket.get("customer", "Customer")
    order_id = ticket.get("order_id", "OD-DYNAMIC-9901")
    active_vertical = vertical_selection if vertical_selection != "Auto-Detect" else ticket.get("vertical", "Food Delivery")
    merchant = ticket.get("merchant", "Partner Merchant")
    cas_score = override_cas
    query_text = custom_query.strip() if custom_query.strip() else ticket.get("default_query", "")

    trace_log = []
    trace_log.append(f"📥 [Ticket Ingested] {ticket_selection} | Order: {order_id} | Vertical: {active_vertical}")
    trace_log.append(f"👤 [Perception] Customer: {user_name} | Swiggy One: {swiggy_one_status} | CAS Score: {cas_score:.2f}")

    # Step 1: Telemetry Inspection
    trace_log.append(f"📡 [Tool Call: Fleet Telemetry] Auditing GPS geofence for order '{order_id}'...")
    telemetry = tool_query_fleet_telemetry(order_id, query_text)
    trace_log.append(f"📍 [Observation] Distance: {telemetry['distance_from_doorstep_meters']}m | Status: {telemetry['geofence_status']}")

    # Step 2: Dark Store / Merchant WMS Inspection
    trace_log.append(f"🏪 [Tool Call: Fulfillment Audit] Checking fulfillment records for {merchant}...")
    fulfillment = tool_inspect_fulfillment_source(order_id, active_vertical)
    trace_log.append(f"📋 [Observation] Facility: {fulfillment['facility_type']} | Status: {fulfillment.get('cold_chain_packaging') or fulfillment.get('wms_bin_status')}")

    # Step 3: Grounded Vector RAG Lookup
    trace_log.append(f"📚 [Action: Domain RAG] Querying Swiggy operations SOPs for: '{query_text[:65]}...'")
    rag_doc = query_swiggy_rag(query_text)
    trace_log.append(f"💡 [Observation] Grounded SOP Clause: {rag_doc['clause_id']} ({rag_doc['category']})")

    # Step 4: Decision Logic & Autonomous Remediation
    is_fraud = cas_score > 0.70
    is_severe_safety = any(w in query_text.lower() for w in ["insect", "foreign", "allergy", "poison", "hospital", "hair", "glass"])

    if is_severe_safety:
        remedy = tool_execute_order_remediation("FOOD_SAFETY_EMERGENCY", order_id)
        trace_log.append(f"🚨 [Tool Call: Trust & Safety] {remedy}")
        action_summary = (
            f"### 📋 MINTO WORK ORDER: {order_id}\n"
            f"**Customer:** {user_name} | **Vertical:** {active_vertical}\n"
            f"**Root Cause:** Food Safety & Contamination Alert (Verified: SOP SWG-SAFE-601)\n\n"
            f"#### 1. Autonomous Actions Taken:\n"
            f"- Issued 100% full refund to original payment source.\n"
            f"- Imposed emergency 2-hour order acceptance hold on merchant kitchen.\n\n"
            f"#### 2. Customer Communication Draft:\n"
            f"\"Dear {user_name}, we take food hygiene with utmost seriousness. A full refund has been credited to your "
            f"account, and our Food Safety Escalations Desk has initiated an urgent operational audit on {merchant}.\""
        )
    elif is_fraud:
        remedy = tool_execute_order_remediation("BLOCK_AND_ESCALATE_TIER2", order_id)
        trace_log.append(f"🚨 [Tool Call: Fraud Risk Engine] {remedy}")
        action_summary = (
            f"### 📋 MINTO WORK ORDER: {order_id}\n"
            f"**Customer:** {user_name} | **Vertical:** {active_vertical}\n"
            f"**Root Cause:** Concession Abuse Threshold Breached (CAS = {cas_score:.2f} > 0.70 limit)\n\n"
            f"#### 1. Autonomous Actions Taken:\n"
            f"- Automated wallet refund blocked per SOP SWG-RISK-405.\n"
            f"- Case flagged for supervisor secondary review with physical item photo validation.\n\n"
            f"#### 2. Customer Communication Draft:\n"
            f"\"Hi {user_name}, thank you for contacting Swiggy. Your claim regarding order {order_id} has been received "
            f"and transferred to our dedicated specialist operations team. An executive will follow up within 30 minutes.\""
        )
    elif telemetry["geofence_status"] == "BREACH_PREMATURE_DROP":
        remedy = tool_execute_order_remediation("TRIGGER_RIDER_IVR_BRIDGE", order_id)
        trace_log.append(f"🚀 [Tool Call: Fleet Dispatch] {remedy}")
        action_summary = (
            f"### 📋 MINTO WORK ORDER: {order_id}\n"
            f"**Customer:** {user_name} | **Vertical:** {active_vertical}\n"
            f"**Root Cause:** Rider Premature Drop Detected (GPS ping was 420m away from coordinates)\n\n"
            f"#### 1. Autonomous Actions Taken:\n"
            f"- Initiated automated IVR bridge to rider under SOP SWG-FLEET-302.\n"
            f"- Placed temporary payout hold pending doorstep delivery pin re-validation.\n\n"
            f"#### 2. Customer Communication Draft:\n"
            f"\"Hi {user_name}, our telemetry detected that your delivery partner marked the order complete outside your "
            f"building gate. We have triggered an automated priority call to the rider to bring your order directly to your door.\""
        )
    elif "Instamart" in active_vertical or "leak" in query_text.lower() or "puncture" in query_text.lower():
        if swiggy_one_status and cas_score < 0.35:
            remedy = tool_execute_order_remediation("DISPATCH_INSTAMART_REPLACEMENT", order_id)
            trace_log.append(f"🚀 [Tool Call: Instamart WMS] {remedy}")
            action_summary = (
                f"### 📋 MINTO WORK ORDER: {order_id}\n"
                f"**Customer:** {user_name} | **Vertical:** Instamart Quick-Commerce\n"
                f"**Root Cause:** Cold-Chain Transit Damage / Leaking Liquid (Verified: SOP SWG-INSTA-204)\n\n"
                f"#### 1. Autonomous Actions Taken:\n"
                f"- Verified Swiggy One membership benefits and clean CAS standing ({cas_score:.2f}).\n"
                f"- Autonomously booked priority 10-minute replacement dispatch from nearest dark store pod.\n\n"
                f"#### 2. Customer Communication Draft:\n"
                f"\"Hi {user_name}, we are so sorry your items arrived damaged! Because you are an active Swiggy One member, "
                f"we have automatically dispatched a fresh replacement order (#OD-INSTA-REP-1101) arriving in 10 minutes. "
                f"Please dispose of the damaged items.\""
            )
        else:
            remedy = tool_execute_order_remediation("INSTANT_WALLET_REFUND", order_id)
            trace_log.append(f"🚀 [Tool Call: Financial Ledger] {remedy}")
            action_summary = (
                f"### 📋 MINTO WORK ORDER: {order_id}\n"
                f"**Customer:** {user_name} | **Vertical:** Instamart Quick-Commerce\n"
                f"**Root Cause:** Quick-Commerce Perishable Defect (Verified: SOP SWG-INSTA-204)\n\n"
                f"#### 1. Autonomous Actions Taken:\n"
                f"- Issued instant wallet refund of damaged items to Swiggy Money Wallet.\n\n"
                f"#### 2. Customer Communication Draft:\n"
                f"\"Hi {user_name}, we sincerely apologize for the damaged items. We have credited a full refund for the affected "
                f"goods directly to your Swiggy Money wallet for immediate use.\""
            )
    else:
        remedy = tool_execute_order_remediation("INSTANT_WALLET_REFUND", order_id)
        trace_log.append(f"🚀 [Tool Call: Financial Ledger] {remedy}")
        action_summary = (
            f"### 📋 MINTO WORK ORDER: {order_id}\n"
            f"**Customer:** {user_name} | **Vertical:** {active_vertical}\n"
            f"**Root Cause:** Missing Item with Tamper Seal Intact (Verified: SOP SWG-FOOD-101)\n\n"
            f"#### 1. Autonomous Actions Taken:\n"
            f"- Issued instant prorated refund of ₹310.00 to Swiggy Money Wallet.\n"
            f"- Protected delivery partner rating; logged omission strike to merchant portal.\n\n"
            f"#### 2. Customer Communication Draft:\n"
            f"\"Hi {user_name}, we are sorry your order was incomplete! We have issued an instant refund of ₹310.00 for the missing "
            f"item to your Swiggy Money wallet.\""
        )

    return "\n\n".join(trace_log), rag_doc["content"], action_summary

# ==============================================================================
# 5. GRADIO INTERFACE DECLARATION WITH EXAMPLES
# ==============================================================================
def populate_ticket_fields(ticket_key: str):
    t = MOCK_SWIGGY_TICKETS[ticket_key]
    return t["default_query"], t["cas_score"], t["membership"], t["vertical"]

with gr.Blocks(theme=gr.themes.Soft(primary_hue="orange")) as demo:
    gr.Markdown("# 🛵 Swiggy Agentic Service Copilot")
    gr.Markdown(
        "Autonomous Customer Support & Hyperlocal Operations Copilot for **Swiggy Food Delivery, "
        "Instamart Dark Stores, and Dineout**. Resolves three-sided platform incidents by linking "
        "vectorized SOPs with fleet telemetry, dark store WMS, and fraud risk engines."
    )

    with gr.Row():
        with gr.Column(scale=1):
            ticket_dropdown = gr.Dropdown(
                choices=list(MOCK_SWIGGY_TICKETS.keys()),
                value=list(MOCK_SWIGGY_TICKETS.keys())[0],
                label="Select Inbound Hyperlocal Incident"
            )
            custom_claim_input = gr.Textbox(
                lines=3,
                value=MOCK_SWIGGY_TICKETS[list(MOCK_SWIGGY_TICKETS.keys())[0]]["default_query"],
                placeholder="Enter custom customer query to test semantic retrieval & dynamic routing...",
                label="Customer Claim / Issue Description"
            )

            with gr.Accordion("⚙️ Telemetry & Customer Risk Controls", open=False):
                cas_slider = gr.Slider(
                    minimum=0.0, maximum=1.0, step=0.01,
                    value=0.12,
                    label="Concession Abuse Score (CAS)"
                )
                swiggy_one_toggle = gr.Checkbox(
                    value=True,
                    label="Active Swiggy One Elite Member"
                )
                vertical_dropdown = gr.Dropdown(
                    choices=["Auto-Detect", "Food Delivery", "Instamart Quick-Commerce", "Dineout", "Swiggy Genie"],
                    value="Auto-Detect",
                    label="Platform Vertical"
                )

            run_btn = gr.Button("⚡ Run Autonomous Hyperlocal Triage", variant="primary")

            gr.Markdown("### 💡 Click to Test Custom Edge Cases:")
            gr.Examples(
                examples=[
                    ["The tamper-evident tape is intact, but the restaurant failed to pack the Paneer Tikka dish!", 0.12, True, "Food Delivery"],
                    ["My milk pouch was punctured and leaking all over the sourdough bread. Completely unusable packaging!", 0.22, True, "Instamart Quick-Commerce"],
                    ["Order is marked 'Delivered' on the app, but no delivery partner ever reached my gate or called me.", 0.18, False, "Food Delivery"],
                    ["Found a sharp piece of glass in the pasta! This is a dangerous hazard and unacceptable!", 0.05, True, "Food Delivery"],
                    ["The chocolate box is dented on the corner. Give me my full cash refund right now without any delay.", 0.84, False, "Instamart Quick-Commerce"],
                    ["Paid via Dineout Pay with card offer, but the 15% discount was not credited on the debited amount.", 0.10, True, "Dineout"]
                ],
                inputs=[custom_claim_input, cas_slider, swiggy_one_toggle, vertical_dropdown],
                label="Pre-Configured Evaluation Queries"
            )

            gr.Markdown("### 📊 Target Operating Metrics")
            gr.Markdown(
                "- **Triage Latency:** Reduced from ~3.5 min to < 25 sec\n"
                "- **Autonomous FCR:** ~40% automated resolution\n"
                "- **Memory Footprint:** < 25 MB RAM (Serverless optimized)\n"
                "- **Zero Hallucination:** Strict grounding on verified Swiggy SOPs"
            )

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("📋 Minto Work Order & Customer Reply"):
                    output_work_order = gr.Markdown()
                with gr.TabItem("🧠 ReAct Agent Operational Trace"):
                    output_trace = gr.Textbox(lines=11, label="Perception, Telemetry, and Tool Logs")
                with gr.TabItem("📖 Grounded Swiggy SOP (RAG)"):
                    output_rag = gr.Textbox(lines=5, label="Retrieved Policy Document")

    ticket_dropdown.change(
        fn=populate_ticket_fields,
        inputs=[ticket_dropdown],
        outputs=[custom_claim_input, cas_slider, swiggy_one_toggle, vertical_dropdown]
    )

    run_btn.click(
        fn=run_swiggy_copilot,
        inputs=[ticket_dropdown, custom_claim_input, cas_slider, swiggy_one_toggle, vertical_dropdown],
        outputs=[output_trace, output_rag, output_work_order]
    )

# ==============================================================================
# 6. COLLISION-PROOF PORT SCANNER & LAUNCH SEQUENCE
# ==============================================================================
def find_available_port(starting_port=7860, max_attempts=50):
    """Scans and returns the first available TCP port to prevent address collisions."""
    for p in range(starting_port, starting_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return starting_port

if __name__ == "__main__":
    is_colab = "google.colab" in sys.modules
    env_port = os.environ.get("PORT")

    if env_port:
        port = int(env_port)
        host = "0.0.0.0"
    else:
        port = find_available_port(7860)
        host = "127.0.0.1"

    print(f"🚀 Starting Swiggy Agentic Copilot on http://{host}:{port}")

    demo.launch(
        server_name=host,
        server_port=port,
        inbrowser=True,
        share=is_colab
    )
