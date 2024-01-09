# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.5.4] - 2024-01-09

### Fixed

- Fixed the issue of bebing unable to rename conversation on Windows
- Switch from text-davinci-003 to using gpt-3.5-turbo-instruct
- When choosing a file path, the default is the root directory

## [0.5.3] - 2024-01-07

### Fixed

- Fixed the error of using the unimported async_wrapper_with_loop in GroupTalkManager.speaking

## [0.5.2] - 2024-01-02

### Fixed

- Fixed the bug that prevents the second conversation from being renamed
- Stop the waiting animation for a conversation when it is deleted
- Fixed the bug where deleting a conversation shows its replies in another window

## [0.5.1] - 2024-01-02

### Fixed

- Fixed the FileNotfoundError when clicking links in MarkdownViewer
- Fixed the KeyError caused by switching to information display when dealing with an empty chat window
- Fixed the bugs in disposable conversation mode caused by openai v1

## [0.5.0] - 2023-12-31

### Added

- Added support for custom plugins.
