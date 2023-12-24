---
draft: false
date: 2023-12-24
categories:
  - DevLog
  - RoadMap
authors:
  - happyapplehorse
---


I've long longed to incorporate a monochrome mode into GPTUI, similar to those vintage single-color green
fluorescent monitors. I find this style not only retro but also futuristic, adding an incredibly cool aesthetic.

![gptui_monochrome](https://raw.githubusercontent.com/happyapplehorse/happyapplehorse-assets/main/gptui/gptui_monochrome.jpeg)

Today, I'm thrilled to announce that this feature has finally been integrated into GPTUI with the release
of v0.4.0. Initially, my ambition was to enable support for user-customizable themes. However, I quickly
realized that the task was more complex than I had imagined. It wasn't just about altering dynamic display
content; I also had to modify existing page layouts. Achieving comprehensive theme settings for all elements
via a configuration file proved to be quite intricate. As a result, for the time being, we've only implemented
this single built-in monochrome theme. But rest assured, plans are in place to introduce more customizable theme
options in the future, allowing users to configure themes directly from a file. The beauty of this monochrome
theme is its dynamic activation capability; you can activate or deactivate it at any moment using the ctrl+o
shortcut. While the mode is undeniably cool, distinguishing certain elements, like user and AI chat content,
can be somewhat challenging in monochrome. Currently, differentiation is based solely on border brightness,
so the ability to easily switch off monochrome mode and revert is essential.

The Textual TUI framework is absolutely marvelous, and I'm so fortunate to have chosen it. While developing the
monochrome mode, I encountered several challenges, and in some instances, I had to employ rather crude and
unsightly methods to achieve my objectives. However, after reaching out for assistance in the Textual Discord
community and receiving invaluable support from the official team, I was able to implement it with grace and
efficiency. The Textual developer community is not only active but also immensely supportive. I've learned a
great deal from their projects and am deeply grateful for the Textual team's beautiful work.

Next, I will write a comprehensive and detailed user guide for GPTUI.
