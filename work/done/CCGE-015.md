# CCGE-015 — Non-UTF-8 config file raises ConfigError

## Goal
load_config turns a UnicodeDecodeError while reading the config file into a ConfigError naming the file.

## Inputs
cottonwood/config.py:41-46,review finding F-correctness-4 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test writes bytes b'\xff\xfe' to a config file and asserts load_config raises ConfigError whose message contains the file path.

All criteria verified 2026-11-20.

## Depends on
_None._
