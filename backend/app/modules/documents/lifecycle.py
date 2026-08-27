"""Lifecycle hooks for the documents module."""

from __future__ import annotations

from app.core.plugins import ModuleContext


async def install(ctx: ModuleContext) -> None:
    """Run on module install."""
    ctx.logger.info("Documents module installed")


async def uninstall(ctx: ModuleContext) -> None:
    """Run on module uninstall."""
    ctx.logger.info("Documents module uninstalling")


async def post_upgrade(ctx: ModuleContext, from_version: str) -> None:
    """Run after a version upgrade."""
    ctx.logger.info(f"Upgrading documents from {from_version}")
