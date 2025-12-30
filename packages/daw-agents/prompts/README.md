# Prompt Governance

All prompts in the DAW system must follow strict versioning and review standards to ensure consistency, reliability, and auditability across agent types.

## Directory Structure

```
prompts/
├── planner/          # Planner agent prompts
├── executor/         # Executor agent prompts
├── validator/        # Validator agent prompts
├── healer/           # Healer agent prompts
└── README.md         # This file
```

## Versioning Standards

All prompts follow **semantic versioning**: `MAJOR.MINOR` (e.g., v1.0, v1.1, v2.0)

### Versioning Rules

- **MAJOR bump** (v1.0 → v2.0): Breaking changes, different output schema, persona change
- **MINOR bump** (v1.0 → v1.1): Enhancements, clarifications, additional constraints
- **All changes** require PR review by designated Prompt Engineers

### File Naming Convention

```
{prompt_name}_v{MAJOR}.{MINOR}.yaml
```

Examples:
- `prd_generator_v1.0.yaml`
- `task_planner_v2.1.yaml`
- `code_validator_v1.2.yaml`

## Required Fields

Every prompt YAML file MUST contain:

### 1. Metadata
```yaml
version: "1.0"           # Semantic version
name: "prompt_name"      # Unique identifier
persona: "Role/Title"    # Agent persona/character
description: "..."       # Short description (1-2 sentences)
```

### 2. System Prompt
```yaml
system_prompt: |
  Multi-line system prompt that defines the agent's behavior,
  constraints, and role-specific guidelines.
```

### 3. Output Schema
```yaml
output_schema:
  type: object
  required: [field1, field2]
  properties:
    field1:
      type: string
      description: "Field description"
    field2:
      type: array
      items:
        type: object
      description: "Array field description"
```

The schema MUST be valid JSON Schema (Draft 7).

### 4. Validation Checklist
```yaml
validation_checklist:
  - Criterion 1
  - Criterion 2
  - Output matches schema exactly
```

## Example Prompt Template

See `planner/prd_generator_v1.0.yaml` for a complete example.

## Review Process

### Creating a New Prompt

1. Create file: `{agent_type}/{name}_v1.0.yaml`
2. Include all required fields
3. Test against validation checklist
4. Create PR for review
5. Designate 2+ Prompt Engineers for review
6. Merge after approval

### Updating an Existing Prompt

- **Non-breaking changes**: Bump MINOR version
- **Breaking changes**: Bump MAJOR version
- Update all references in code
- Document changes in PR description
- Require approval before merge

## Storage & Retrieval

### Prompt Loader
Prompts are loaded by the system via:
```python
from daw_agents.prompts import load_prompt

prompt = load_prompt("planner", "prd_generator", "1.0")
```

### Prompt Registry
A central registry tracks all available prompts:
```json
{
  "planner": {
    "prd_generator": ["1.0", "1.1"],
    "task_planner": ["1.0"]
  },
  "executor": {
    "code_generator": ["1.0"]
  }
}
```

## Best Practices

1. **Be Specific**: Prompts should be specific to agent type and use case
2. **Include Examples**: Consider including examples in system_prompt for clarity
3. **Define Boundaries**: Clearly state what the agent should NOT do
4. **Version Aggressively**: Create new versions for any material changes
5. **Test Thoroughly**: Validate output against schema before deploying
6. **Document Rationale**: Explain "why" in PR descriptions

## Governance Rules

- All prompts require version tags
- No unversioned prompts in production
- All changes tracked in Git history
- PR review mandatory for any changes
- Validation checklist completion required before merge
- Schema validation required in test suite

## Related Documents

- Architecture: `docs/planning/architecture/`
- Agent Specifications: `agents.md`
- Definition of Done: `docs/planning/stories/definition_of_done.md`
