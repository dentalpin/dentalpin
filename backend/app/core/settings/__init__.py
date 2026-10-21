"""Generic clinic-scoped settings registry (ADR 0041).

Modules declare settings through ``BaseModule.get_settings()``; this
package validates the declarations, stores values under
``clinics.settings[<module>][<key>]`` and serves them through
``/api/v1/settings/{module}``.
"""
