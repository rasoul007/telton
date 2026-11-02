"""Telton — automated sports-news video agent (Persian / fa-IR).

Pipeline: collect -> rundown -> voice -> render -> review -> approve -> publish
Every stage reads and writes plain files inside a *project* directory so a
human (or Cline) can inspect and edit anything between stages.
"""

__version__ = "0.1.0"
