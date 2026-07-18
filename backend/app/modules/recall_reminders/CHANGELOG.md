# Changelog — recall_reminders module

## Unreleased

- Initial version: subscribes to `RECALL_CREATED`, enqueues a
  `recall_reminder` notification via the existing gateway. No models,
  no UI — pure connector.
