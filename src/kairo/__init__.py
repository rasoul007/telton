"""KAIRO Episode 01 production pipeline.

Modules
-------
screenplay : load / validate / merge the 25-scene screenplay
prompts    : compile per-scene image + video generation prompts
voice      : Persian voice-over generation (edge-tts, fa-IR-FaridNeural)
music      : procedural score and sound-design bed
figure     : procedural KAIRO stickman renderer
backdrops  : procedural environments (room, savanna, cave)
render     : stills -> 12s clips -> 300s film, plus subtitles and QC
"""

__version__ = "1.0.0"
