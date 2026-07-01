# Reviewer Report

**Paper Title:** *Non-Destructive Reverse Engineering of a Closed
Android--ROS Service Robot: Open ROSBridge Integration and Edge
Conversational Stack Without Vendor Support*

## Summary

This paper presents CYBEL, an open platform obtained through the
non-destructive reverse engineering of a proprietary Android-based
service robot. The work reconstructs ROSBridge communication, analyzes
the vendor Android applications, rebuilds navigation and teleoperation
interfaces, and proposes an edge conversational architecture independent
of the manufacturer.

The engineering effort is significant and the topic is highly relevant
for robotics practitioners facing closed commercial platforms. However,
in its current form, the manuscript resembles an engineering project
report more than a research paper. The scientific positioning,
experimental validation, and generalization of the proposed methodology
require substantial strengthening.

------------------------------------------------------------------------

# Overall Recommendation

**Recommendation:** Borderline Accept (ROSCon) / Reject (ICRA-IROS in
current state)

**Confidence:** High

------------------------------------------------------------------------

# Scores

  ------------------------------------------------------------------------
  Criterion                 Score (/5)                Comments
  ------------------------- ------------------------- --------------------
  Originality               5                         Highly original
                                                      topic.

  Technical Quality         4                         Strong engineering
                                                      implementation.

  Scientific Contribution   3                         Contributions need
                                                      stronger
                                                      abstraction.

  Experimental Validation   2                         Too few quantitative
                                                      experiments.

  Reproducibility           4                         Methodology is
                                                      mostly reproducible.

  Writing Quality           4                         Well written
                                                      overall.

  Impact                    4                         Potentially high
                                                      impact if revised.
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# Strengths

## 1. Originality

Reverse engineering a proprietary Android service robot without vendor
documentation is novel and addresses a real interoperability problem.

## 2. Significant Engineering Effort

The paper demonstrates: - network discovery; - APK reverse
engineering; - ROSBridge reconstruction; - Android integration; - edge
deployment; - conversational interface.

This represents a substantial amount of engineering work.

## 3. Clear Storytelling

The manuscript follows a logical progression: 1. Closed robot. 2.
Reverse engineering. 3. Protocol reconstruction. 4. Open architecture.
5. Validation.

## 4. Practical Relevance

Many laboratories own commercial robots that cannot be customized. The
proposed methodology is therefore valuable.

------------------------------------------------------------------------

# Major Weaknesses

## 1. The scientific contribution is not sufficiently emphasized

The paper often presents CYBEL as the contribution.

I believe the actual contribution is:

> A methodology for reverse engineering closed Android-based service
> robots.

CYBEL should be presented as the validation platform.

------------------------------------------------------------------------

## 2. Missing Related Work

The manuscript lacks a dedicated Related Work section.

It should discuss:

-   reverse engineering robotics;
-   Android reverse engineering;
-   ROSBridge;
-   interoperability;
-   vendor lock-in;
-   edge robotics;
-   conversational robotics.

Without this section, reviewers cannot position the contribution.

------------------------------------------------------------------------

## 3. Insufficient Experimental Validation

The evaluation section is currently too limited.

The paper should report:

-   number of experiments;
-   success rate;
-   failure rate;
-   localization accuracy;
-   navigation time;
-   teleoperation latency;
-   ROSBridge throughput;
-   packet loss;
-   recovery time;
-   comparison between navigation strategies.

------------------------------------------------------------------------

## 4. Lack of Comparison with the Vendor Solution

One of the strongest claims is that CYBEL replaces the proprietary
application.

However, there is no direct comparison.

A feature comparison table would considerably strengthen the paper.

Suggested comparison:

  Feature             Vendor   CYBEL
  ------------------- -------- -------
  Teleoperation       ✓        ✓
  Guided Tour         ✓        ✓
  FAQ                 ✓        ✓
  Offline             ✗        ✓
  Extensible          ✗        ✓
  Cloud Independent   ✗        ✓

------------------------------------------------------------------------

## 5. Too Many Implementation Details

The manuscript frequently mentions script names and internal filenames.

Research papers should describe concepts rather than source files.

Example:

Instead of

-   phase0_robot_check.py

use

-   Validation Framework.

------------------------------------------------------------------------

## 6. Reverse Engineering Should Dominate the Paper

Currently the reverse engineering process occupies a relatively small
portion of the manuscript.

I recommend expanding:

-   discovery process;
-   failed hypotheses;
-   protocol reconstruction;
-   verification methodology;
-   lessons learned.

------------------------------------------------------------------------

## 7. Conversational Layer

The title promises an edge conversational stack.

However, only a limited part of the paper discusses it.

Either: - expand this section, or - reduce its importance in the title.

------------------------------------------------------------------------

# Minor Comments

-   Add a pipeline figure summarizing the complete reverse engineering
    workflow.
-   Quantify all qualitative claims.
-   Explain H4 in more detail.
-   Improve terminology consistency.
-   Discuss ethical aspects of reverse engineering more thoroughly.
-   Clarify reproducibility artifacts.

------------------------------------------------------------------------

# Questions for the Authors

1.  How many ROS topics were ultimately reconstructed?
2.  How long did the reverse engineering process take?
3.  How many APKs were analyzed?
4.  Can the methodology be generalized to other robots?
5.  Which parts remain vendor-specific?
6.  Why was ROSBridge selected over alternative interfaces?
7.  How reproducible is the methodology?

------------------------------------------------------------------------

# Suggested Reorganization

1.  Introduction
2.  Related Work
3.  Robot Architecture
4.  Reverse Engineering Methodology
5.  Protocol Reconstruction
6.  CYBEL Architecture
7.  Experimental Evaluation
8.  Discussion
9.  Conclusion

------------------------------------------------------------------------

# Final Assessment

The engineering quality is excellent and the originality is undeniable.

Nevertheless, the manuscript currently reads as an advanced engineering
report instead of a research article.

The strongest opportunity for improvement is to shift the focus from the
software platform (CYBEL) toward the general reverse engineering
methodology.

Doing so would considerably increase the scientific value and the
likelihood of acceptance in international robotics venues.
