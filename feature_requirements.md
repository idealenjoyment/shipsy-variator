SHIPSY ENGINEERING | Take-Home Assignment
TAKE-HOME ASSIGNMENT
Build an Experiment Assignment Library
Language of your choice | AI tools allowed | Submit via GitHub
What to Build
When running experiments across a product - testing different algorithms, pricing models, UI
changes - you need to deterministically assign users to variants and serve them a consistent
experience.
Build a library that does exactly one thing well: given an experiment and a user, return the variant
that user belongs to.
The API
Your library should expose a single primary function:
•
•
•
•
experiment.getVariant(experimentKey, userId)
Returns a variantId string - e.g.
'v1'
'v2'
,
, or whatever the experiment defines
The same userId must always get the same variantId for a given experimentKey
Traffic should be split across variants according to their configured weights
If an experiment does not exist or is inactive, return null
Experiment Configuration
Your library needs to know about experiments somehow - the keys, the variants, how traffic is split.
How it gets that information is up to you.
Think about what interface makes the most sense. What does the developer using this library need
to express, and what's the cleanest way for them to provide it? The schema and the ingestion
mechanism are both part of the design problem.
Whatever approach you choose, document it clearly in your README and be ready to explain why.
Constraints
•
•
No per-user state - you cannot store which variant a user was assigned to. The assignment
must be derived purely from the inputs.
Stateless and deterministic - calling getVariant 1000 times for the same inputs must return the
same result every time, with no side effects
Confidential - Please do not share
SHIPSY ENGINEERING | Take-Home Assignment
•
Do not use an A/B testing or feature flagging SDK - the assignment logic should be your own.
Any other packages are fine.
Example
To illustrate the expected behaviour - given an experiment with two variants splitting traffic 80/20:
experiment.getVariant("checkout_flow", "user_123") // always returns same variant
experiment.getVariant("checkout_flow", "user_456") // always returns same variant
experiment.getVariant("checkout_flow", "user_123") // same as first call
Across a large population of users, roughly 80% should land in one variant and 20% in the other.
The exact user-to-variant mapping is up to your implementation - what matters is consistency and
approximate distribution.
Bonus (only if time allows)
•
Targeting: User targeting
◦
Allow an experiment to target only a subset of users based on attributes - e.g. only users on a
certain plan or in a certain region
Please Don't Build
•
•
•
No HTTP API or dashboard
No database or remote config fetch as part of the core assignment logic
No analytics or event tracking
What to Submit
Share a GitHub repo (private is fine - add us as collaborators) with:
1. The library
◦
◦
2. Tests
Working, importable code
Use whatever language you're most comfortable with
◦
Cover: correct variant returned, consistency across multiple calls for the same user, approximate
distribution across a large user population
◦
The consistency test is the most important one
3. A README
◦
How to run the code and tests
◦
◦
◦
◦
A short usage example
How you approached consistent assignment - the core problem
How experiments are provided to the library - your interface design and why
What you'd change or add with more time
Confidential - Please do not share
SHIPSY ENGINEERING | Take-Home Assignment
◦
How you used AI - what it helped with, what you changed
On Using AI
Encouraged - just be honest about it
Use whatever AI tools you normally work with. In your README, include a short note: what did you
ask AI to help with, where did you override it, and is there anything in the code you'd want to revisit?
We'll walk through the implementation together after you submit, so be ready to explain every
decision.
What Good Looks Like
A strong solution goes beyond correctness. Here is how we think about the problem:
Correctness over completeness
Consistent assignment and an approximately correct distribution matter far more than bonus
features. Get the core right before reaching for anything else.
Consistency is a hard requirement
An experiment system that assigns users to different variants on different calls is worse than
useless - it actively corrupts your data. Think carefully about what guarantees your approach
provides and be explicit about them.
Design for the caller
The engineer configuring an experiment should not need to understand your internals. The config
schema and the API should be obvious. Complexity lives inside the library, not outside it.
Distribution quality
Weights of 50/50 should produce a roughly even split across a large population, not 70/30. Think
about whether your assignment mechanism produces a uniform distribution and how you'd verify it.
Explain your tradeoffs
There are real choices here - how you derive the assignment from the inputs, how you map that to a
variant given arbitrary weights, what your config schema expresses and what it doesn't. What
matters is that you made deliberate choices and can explain why.
Confidential - Please do not share
SHIPSY ENGINEERING | Take-Home Assignment
A clean, working implementation with clear reasoning beats a sprawling one with no explanation.
We're looking forward to seeing how you think.
Good luck - feel free to reach out if anything is unclear.
Confidential - Please do not share
