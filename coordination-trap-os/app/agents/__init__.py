"""Agent registry — organizational-service agents for the Relationship & Events OS."""
from .strategy import StrategyAgent
from .relationship_intelligence import RelationshipIntelligenceAgent
from .community_intelligence import CommunityIntelligenceAgent
from .topic_development import TopicDevelopmentAgent
from .network_gap import NetworkGapAgent
from .event_matching import EventMatchingAgent
from .invitation import InvitationAgent
from .event_operations import EventOperationsAgent
from .relationship_facilitator import RelationshipFacilitatorAgent
from .post_event_knowledge import PostEventKnowledgeAgent
from .risk_watcher import RiskWatcherAgent
from .decision_facilitator import DecisionFacilitatorAgent
from .documentation_steward import DocumentationStewardAgent

STRATEGY = StrategyAgent()
RELATIONSHIP_INTELLIGENCE = RelationshipIntelligenceAgent()
COMMUNITY_INTELLIGENCE = CommunityIntelligenceAgent()
TOPIC_DEVELOPMENT = TopicDevelopmentAgent()
NETWORK_GAP = NetworkGapAgent()
EVENT_MATCHING = EventMatchingAgent()
INVITATION = InvitationAgent()
EVENT_OPERATIONS = EventOperationsAgent()
RELATIONSHIP_FACILITATOR = RelationshipFacilitatorAgent()
POST_EVENT_KNOWLEDGE = PostEventKnowledgeAgent()
RISK_WATCHER = RiskWatcherAgent()
DECISION_FACILITATOR = DecisionFacilitatorAgent()
DOCUMENTATION_STEWARD = DocumentationStewardAgent()

__all__ = [
    "STRATEGY", "RELATIONSHIP_INTELLIGENCE", "COMMUNITY_INTELLIGENCE", "TOPIC_DEVELOPMENT",
    "NETWORK_GAP", "EVENT_MATCHING", "INVITATION", "EVENT_OPERATIONS",
    "RELATIONSHIP_FACILITATOR", "POST_EVENT_KNOWLEDGE",
    "RISK_WATCHER", "DECISION_FACILITATOR", "DOCUMENTATION_STEWARD",
]
