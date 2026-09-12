"""Curated topic knowledge used by the offline provider.

The offline provider exists so the whole product is runnable and testable with no
API key. Its output is templated rather than generated, so it leans on this small
hand-written map to stay specific instead of producing filler.
"""

from __future__ import annotations

# keyword -> (expected answer points, practice problems, study resources)
TOPIC_KNOWLEDGE: dict[str, dict[str, list[str]]] = {
    "sql": {
        "points": [
            "Explains how an index changes the lookup from a scan to a seek",
            "Mentions join strategies (nested loop, hash, merge) and when each wins",
            "Discusses selectivity and why an index on a low-cardinality column helps little",
            "Mentions reading the query plan (EXPLAIN / EXPLAIN ANALYZE)",
        ],
        "problems": [
            "Write a query finding the second-highest salary per department",
            "Optimise a slow report query using a composite index",
        ],
        "resources": [
            "PostgreSQL docs: 'Using EXPLAIN' and 'Index Types'",
            "Use The Index, Luke - chapters on concatenated indexes",
        ],
    },
    "database": {
        "points": [
            "Covers normalisation and where denormalisation is deliberately chosen",
            "Explains transactions and the isolation level in use",
            "Discusses how the schema handles growth and hot rows",
        ],
        "problems": [
            "Design a schema for a multi-tenant booking system",
            "Model a social graph and justify the storage engine",
        ],
        "resources": [
            "Designing Data-Intensive Applications - chapters 2 and 7",
        ],
    },
    "api": {
        "points": [
            "Chooses resource-oriented paths and correct HTTP verbs and status codes",
            "Addresses pagination, filtering, and versioning",
            "Covers authentication and authorisation on each endpoint",
            "Mentions idempotency for retryable writes",
        ],
        "problems": [
            "Design a paginated REST API with cursor-based pagination",
            "Make a payment endpoint safely retryable",
        ],
        "resources": [
            "MDN HTTP status code reference",
            "FastAPI docs: dependencies and security",
        ],
    },
    "python": {
        "points": [
            "Distinguishes mutable from immutable types and the aliasing consequences",
            "Explains generators and when laziness matters for memory",
            "Mentions the GIL and what it does and does not prevent",
            "Uses context managers for resource cleanup",
        ],
        "problems": [
            "Implement an LRU cache without functools",
            "Write a generator pipeline that streams a large file",
        ],
        "resources": [
            "Fluent Python - chapters on data model and iterables",
            "Python docs: contextlib and itertools",
        ],
    },
    "javascript": {
        "points": [
            "Explains the event loop, microtasks, and task ordering",
            "Covers closures and how they capture scope",
            "Distinguishes promises from async/await error handling",
        ],
        "problems": [
            "Implement a promise-based retry with exponential backoff",
            "Write a debounce and a throttle and explain the difference",
        ],
        "resources": [
            "MDN: Concurrency model and the event loop",
        ],
    },
    "react": {
        "points": [
            "Explains re-render triggers and how state updates batch",
            "Correctly describes useEffect dependencies and cleanup",
            "Discusses lifting state versus context versus a store",
            "Mentions keys and list reconciliation",
        ],
        "problems": [
            "Build a debounced search input with cancellation on unmount",
            "Refactor prop drilling into context without over-rendering",
        ],
        "resources": [
            "React docs: 'You Might Not Need an Effect'",
        ],
    },
    "system design": {
        "points": [
            "States the load and data-size assumptions before designing",
            "Covers the read/write path separately",
            "Identifies the bottleneck and the scaling strategy for it",
            "Discusses failure modes and what degrades first",
        ],
        "problems": [
            "Design a URL shortener handling 10k writes/sec",
            "Design a notification fan-out service",
        ],
        "resources": [
            "Designing Data-Intensive Applications - chapters 1 and 5",
        ],
    },
    "testing": {
        "points": [
            "Separates unit, integration, and end-to-end and says what each catches",
            "Explains what is mocked and why that boundary was chosen",
            "Mentions test data setup and isolation between tests",
        ],
        "problems": [
            "Write tests for a function with a network dependency",
            "Design an integration test suite that runs without live services",
        ],
        "resources": [
            "pytest docs: fixtures and parametrisation",
        ],
    },
    "docker": {
        "points": [
            "Explains image layers and what invalidates the build cache",
            "Distinguishes images, containers, and volumes",
            "Mentions multi-stage builds for smaller images",
        ],
        "problems": [
            "Write a multi-stage Dockerfile for a Python service",
        ],
        "resources": [
            "Docker docs: best practices for writing Dockerfiles",
        ],
    },
    "machine learning": {
        "points": [
            "Describes the train/validation/test split and why it matters",
            "Identifies overfitting and the regularisation used",
            "Chooses a metric appropriate to the class balance",
        ],
        "problems": [
            "Diagnose a model with high training and low validation accuracy",
        ],
        "resources": [
            "scikit-learn user guide: model evaluation",
        ],
    },
    "algorithms": {
        "points": [
            "States the time and space complexity and justifies it",
            "Handles the edge cases (empty, single element, duplicates)",
            "Explains the choice of data structure",
        ],
        "problems": [
            "Two-sum and its hash-map optimisation",
            "Merge k sorted lists with a heap",
        ],
        "resources": [
            "Introduction to Algorithms - chapters on sorting and hashing",
        ],
    },
}

# Fallback used when a topic matches nothing above.
GENERIC_KNOWLEDGE = {
    "points": [
        "Gives a concrete example rather than staying abstract",
        "Explains the trade-offs of the approach taken",
        "Describes how the result was verified",
        "States what they would do differently now",
    ],
    "problems": [
        "Rebuild a component of your last project and document the trade-offs",
    ],
    "resources": [
        "The official documentation for the primary tool in this area",
    ],
}


def knowledge_for(topic: str) -> dict[str, list[str]]:
    """Best-effort lookup of curated knowledge for a topic string."""
    lowered = topic.lower()
    for key, value in TOPIC_KNOWLEDGE.items():
        if key in lowered:
            return value
    # Try the reverse direction: a single-word topic inside a longer key.
    for key, value in TOPIC_KNOWLEDGE.items():
        if any(part in key for part in lowered.split() if len(part) > 3):
            return value
    return GENERIC_KNOWLEDGE
