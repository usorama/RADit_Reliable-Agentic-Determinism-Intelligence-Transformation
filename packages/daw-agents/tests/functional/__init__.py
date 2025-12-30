"""Functional tests for DAW agent pipeline.

Functional tests validate the complete agent workflow:
1. PRD parsing and task decomposition (Planner)
2. Code generation (Executor/Developer)
3. Test validation (Validator)
4. Integration testing (UAT)

These tests use the "dogfood" approach - using DAW to build real applications.
"""
