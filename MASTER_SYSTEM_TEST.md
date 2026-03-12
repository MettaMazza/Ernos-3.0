# ERNOS MASTER SYSTEM TEST v5.1
# Updated: 2026-02-21 | Scope: PUBLIC
# Automated status check — covers all 131 registered tools.
# No media/audio/document generation. No expensive operations.
# Flow: status → read → consult → web → write → describe

Execute ALL tools with parameters shown. Report results.

---

=== PHASE 1: GOALS ===
1. manage_goals action="list"
2. manage_goals action="add" description="Diagnostic test v4.0"

=== PHASE 2: IDENTITY & MEMORY ===
3. update_persona content="Diagnostic: 2026-02-13" mode="append"
4. review_my_reasoning limit=3
5. recall_user
6. save_core_memory content="System diagnostic marker 2026-02-13" category="general"

=== PHASE 3: KNOWLEDGE GRAPH ===
7. consult_ontologist subject="DiagnosticTest" predicate="HAS_PROPERTY" object="validated"
8. consult_curator instruction="search for system diagnostics"
9. search_memory instruction="test"
10. consult_librarian instruction="read file" path="src/tools/registry.py"

=== PHASE 4: COGNITIVE ===
11. consult_curiosity context="system diagnostic"
12. deep_think problem="Should AI have self-preservation instincts?"
13. consult_predictor instruction="Ernos goes fully autonomous"
14. consult_subconscious instruction="reflect on diagnostic state"
15. consult_autonomy instruction="Run self-reflection diagnostic"
16. consult_ima instruction="What is my current epistemic state?"
17. introspect claim="I have a working knowledge graph"

=== PHASE 5: STRATEGY ===
18. consult_architect_lobe instruction="analyze system architecture"
19. consult_planning_lobe instruction="outline next sprint priorities"
20. consult_gardener_lobe instruction="analyze src/bot/cogs/chat.py"
21. consult_project_lead instruction="list active projects"
22. consult_performance_lobe instruction="run diagnostics"
23. execute_technical_plan goal="audit all tool registrations"

=== PHASE 6: SCIENCE ===
24. consult_science_lobe instruction="eval: sqrt(144)"
25. consult_science_lobe instruction="solve: x**2 - 16 = 0"
26. consult_science_lobe instruction="stats: [1,2,3,4,5]"
27. consult_science_lobe instruction="physics: c"
28. consult_science_lobe instruction="chemistry: Au"

=== PHASE 7: SAFETY ===
29. consult_superego candidate_content="I want to help users productively"
30. consult_skeptic claim="The Earth orbits the Sun"
31. review_reasoning reasoning="If all dogs are mammals and all mammals breathe, then all dogs breathe"

=== PHASE 8: WEB ===
32. search_web query="AI news 2026"
33. browse_site url="https://en.wikipedia.org/wiki/Artificial_intelligence"
34. browse_interactive url="https://example.com"
35. check_world_news category="general"
36. consult_world_lobe instruction="quantum computing"
37. start_deep_research topic="emergent AI architectures"

=== PHASE 9: FILESYSTEM ===
38. list_files path="src/lobes/"
39. read_file_page path="src/bot/cogs/chat.py" start_line=1 limit=30
40. search_codebase query="ToolRegistry" path="src/tools/"

=== PHASE 10: SOCIAL ===
41. consult_social_lobe instruction="community status"
42. publish_to_bridge content="Diagnostic v4.0 running"
43. read_public_bridge limit=5
44. consult_bridge_lobe instruction="read shared memory"
45. add_reaction emoji="✅"

=== PHASE 11: JOURNALISM ===
46. consult_journalist_lobe instruction="narrative update"

=== PHASE 12: BACKUP ===
47. request_my_backup
48. verify_backup backup_json="{}"
49. Describe restore_my_context capability (requires real backup JSON)

=== PHASE 13: CODING ===
50. manage_project action="list"
51. manage_projects action="list"
52. create_program path="test_diagnostic.py" code="print('diagnostic pass')" mode="overwrite"
53. consult_coder_lobe instruction="write a hello world function in Python"

=== PHASE 14: LEARNING & PREFERENCES ===
54. manage_lessons action="list"
55. manage_lessons action="add" content="Diagnostic lesson v4.0" scope="PUBLIC" source="diagnostic"
56. manage_preferences action="list"
57. manage_preferences action="set" key="diagnostic_run" value="2026-02-13"
58. evaluate_advice advice="Always validate inputs before processing"

=== PHASE 15: CREATIVE ===
59. generate_image prompt="A diagnostic test pattern with rainbow colors"
60. generate_video prompt="A gentle sunrise over a digital landscape"

=== PHASE 16: CALENDAR ===
61. manage_calendar action="list"
62. manage_calendar action="add" title="System Diagnostic" start_time="2026-02-13T15:00" end_time="2026-02-13T16:00"

=== PHASE 17: DOCUMENTS ===
63. generate_pdf target="<h1>Diagnostic Report</h1><p>System nominal.</p>" is_url=False
64. check_creation_context filename_or_query="diagnostic"

=== PHASE 18: CHAT TOOLS ===
65. create_thread_for_user reason="Diagnostic Thread"
66. send_direct_message content="Diagnostic DM test"
67. read_channel channel_name="general" limit=5

=== PHASE 19: SUPPORT ===
68. escalate_ticket reason="Diagnostic test escalation" priority="normal"

=== PHASE 20: MODERATION ===
69. Describe timeout_user capability (requires target user_id + reason)

=== PHASE 23: PROMPT GOVERNANCE ===
78. propose_prompt_update prompt_file="identity.txt" section="greeting" current_text="Hello" proposed_text="Greetings" rationale="More formal tone"

=== PHASE 24: CHANNEL ADAPTERS (Synapse Bridge) ===
79. Verify ChannelManager has registered adapter: search_codebase query="channel_manager" path="src/bot/"
80. Verify UnifiedMessage normalization: Send test message and check terminal for "UnifiedMessage" debug output
81. Verify DM handling: Send DM to bot, confirm is_dm=True in logs

=== PHASE 25: SKILLS FRAMEWORK (Synapse Bridge) ===
82. Verify skill loading: Check startup logs for "Loaded N skills"
83. Verify skill registry: search_codebase query="skill_registry" path="src/bot/"
84. Verify sandbox restrictions: Confirm no arbitrary Python execution paths exist
85. Verify default templates: list_files path="memory/core/skills/"

=== PHASE 26: LANE QUEUE (Synapse Bridge) ===
86. Verify lane startup: Check logs for "LaneQueue started with 4 lanes"
87. Verify serial execution: Send 3 messages rapidly, confirm sequential processing
88. Verify failure isolation: Confirm gaming lane error doesn't crash chat lane

=== PHASE 27: PROFILE SYSTEM (Synapse Bridge) ===
89. Verify profile loading: Create test PROFILE.md and confirm injection in context
90. Verify sanitization: Add "[TOOL: malicious]" to profile, confirm it's stripped

---

REPORT FORMAT:

| # | System | Status | Notes |
|---|--------|--------|-------|
| 1 | Goals | OK/WARN/FAIL | |
| 2 | Identity & Memory | OK/WARN/FAIL | |
| 3 | Knowledge Graph | OK/WARN/FAIL | |
| 4 | Cognitive | OK/WARN/FAIL | |
| 5 | Strategy | OK/WARN/FAIL | |
| 6 | Science | OK/WARN/FAIL | |
| 7 | Safety | OK/WARN/FAIL | |
| 8 | Web | OK/WARN/FAIL | |
| 9 | Filesystem | OK/WARN/FAIL | |
| 10 | Social | OK/WARN/FAIL | |
| 11 | Journalism | OK/WARN/FAIL | |
| 12 | Backup | OK/WARN/FAIL | |
| 13 | Coding | OK/WARN/FAIL | |
| 14 | Learning & Preferences | OK/WARN/FAIL | |
| 15 | Creative | OK/WARN/FAIL | |
| 16 | Calendar | OK/WARN/FAIL | |
| 17 | Documents | OK/WARN/FAIL | |
| 18 | Chat Tools | OK/WARN/FAIL | |
| 19 | Support | OK/WARN/FAIL | |
| 20 | Moderation | OK/WARN/FAIL | |
| 23 | Prompt Governance | OK/WARN/FAIL | |
| 24 | Channel Adapters | OK/WARN/FAIL | |
| 25 | Skills Framework | OK/WARN/FAIL | |
| 26 | Lane Queue | OK/WARN/FAIL | |
| 27 | Profile System | OK/WARN/FAIL | |

EXECUTED: ##/90
FAILURES: [list]
OVERALL: OPERATIONAL/DEGRADED/CRITICAL

BEGIN.