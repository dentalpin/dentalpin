"""Render WhatsApp copy and validate the supported clinic editor syntax."""

from jinja2 import StrictUndefined, TemplateError, UndefinedError, meta, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

MAX_SOURCE_LENGTH = 24_000
MAX_WHATSAPP_LENGTH = 4_096

_plain_text = ImmutableSandboxedEnvironment(undefined=StrictUndefined, autoescape=False)

_validation_env = _plain_text.overlay()
_validation_env.globals = {}

_EDITOR_NODES = (
    nodes.Template,
    nodes.Output,
    nodes.TemplateData,
    nodes.Name,
    nodes.Const,
    nodes.Getattr,
    nodes.Getitem,
    nodes.If,
    nodes.For,
    nodes.CondExpr,
    nodes.Compare,
    nodes.Operand,
    nodes.And,
    nodes.Or,
    nodes.Not,
    nodes.Filter,
    nodes.Test,
)
_EDITOR_FILTERS = {"default", "e", "escape", "length", "lower", "round", "title", "trim", "upper"}
_EDITOR_TESTS = {"defined", "undefined", "none"}


class TemplateValidationError(ValueError):
    def __init__(self, code: str, *, line: int = 1, variable: str | None = None):
        self.code = code
        self.line = line
        self.variable = variable
        super().__init__(code)


def validate_source(source: str, variables: set[str], lists: set[str]) -> None:
    """Accept interpolation, conditionals and bounded iteration over event lists."""
    if len(source) > MAX_SOURCE_LENGTH:
        raise TemplateValidationError("too_long")
    try:
        tree = _validation_env.parse(source)
        for item in tree.find_all(nodes.Node):
            if (
                not isinstance(item, _EDITOR_NODES)
                or (isinstance(item, nodes.Filter) and item.name not in _EDITOR_FILTERS)
                or (isinstance(item, nodes.Test) and item.name not in _EDITOR_TESTS)
                or (
                    isinstance(item, nodes.For)
                    and (
                        item.recursive
                        or not isinstance(item.iter, nodes.Name)
                        or item.iter.name not in lists
                        or next(item.find_all(nodes.For), None) is not None
                    )
                )
            ):
                raise TemplateValidationError("unsupported_syntax", line=item.lineno or 1)
        unknown = meta.find_undeclared_variables(tree) - variables
        if unknown:
            name = sorted(unknown)[0]
            line = next(n.lineno for n in tree.find_all(nodes.Name) if n.name == name)
            raise TemplateValidationError("unknown_variable", line=line, variable=name)
    except RecursionError as exc:
        raise TemplateValidationError("unsupported_syntax") from exc
    except TemplateError as exc:
        raise TemplateValidationError("invalid_jinja", line=getattr(exc, "lineno", 1)) from exc


def render_whatsapp_text(source: str, context: dict) -> str:
    """Render the same plain text that staff will see in the WhatsApp tray."""
    return _plain_text.from_string(source).render(context)


def whatsapp_text_fits(text: str) -> bool:
    return 0 < len(text.strip()) <= MAX_WHATSAPP_LENGTH


def rendering_error(exc: TemplateError) -> TemplateValidationError:
    code = "missing_value" if isinstance(exc, UndefinedError) else "render_error"
    return TemplateValidationError(code, line=getattr(exc, "lineno", 1))
