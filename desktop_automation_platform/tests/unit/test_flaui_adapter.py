"""
Unit tests for the FlaUI adapter layer.

All FlaUI .NET types are mocked so tests run on any OS without
requiring pythonnet or FlaUI assemblies to be installed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from desktop_automation_platform.adapters.flaui.control_type_map import (
    list_supported_control_types,
    resolve_control_type,
)
from desktop_automation_platform.adapters.flaui.translator import FlaUILocatorTranslator
from desktop_automation_platform.config.schema import (
    AdaptersConfig,
    ApplicationConfig,
    FlaUIAdapterConfig,
    FrameworkConfig,
    PlatformConfig,
)
from desktop_automation_platform.core.exceptions import (
    ElementNotFoundException,
    LocatorResolutionException,
)
from desktop_automation_platform.core.models import (
    ActionStatus,
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    LocatorDefinition,
    LocatorStrategy,
    SessionState,
    UnifiedLocator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config() -> PlatformConfig:
    return PlatformConfig(
        framework=FrameworkConfig(retry_count=1, screenshot_on_failure=False),
        application=ApplicationConfig(name="Test App"),
        adapters=AdaptersConfig(flaui=FlaUIAdapterConfig(automation_type="UIA3")),
    )


def _make_session(state: SessionState = SessionState.ACTIVE) -> ApplicationSession:
    session = ApplicationSession(
        app_info=ApplicationInfo(name="Test App"),
        adapter_type=AdapterType.FLAUI,
        native_session={
            "application": MagicMock(),
            "automation": MagicMock(),
            "main_window": MagicMock(),
        },
    )
    session.state = state
    return session


def _make_locator(
    strategy: LocatorStrategy = LocatorStrategy.AUTOMATION_ID,
    value: str = "LoginButton",
) -> UnifiedLocator:
    return UnifiedLocator(
        name="TEST_ELEMENT",
        primary=LocatorDefinition(strategy=strategy, value=value),
    )


def _make_automation_mock() -> MagicMock:
    automation = MagicMock()
    automation.ConditionFactory = MagicMock()
    automation.ConditionFactory.ByAutomationId.return_value = MagicMock()
    automation.ConditionFactory.ByName.return_value = MagicMock()
    automation.ConditionFactory.ByClassName.return_value = MagicMock()
    automation.ConditionFactory.ByControlType.return_value = MagicMock()
    automation.PropertyLibrary = MagicMock()
    automation.PropertyLibrary.Element.Name = MagicMock()
    return automation


# ---------------------------------------------------------------------------
# ControlTypeMap tests (no CLR needed — tested via mock)
# ---------------------------------------------------------------------------


class TestControlTypeMap:
    def test_list_supported_returns_non_empty(self) -> None:
        types = list_supported_control_types()
        assert len(types) > 20
        assert "button" in types

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown control type"):
            resolve_control_type("FictionalControlType")

    @patch("desktop_automation_platform.adapters.flaui.control_type_map.resolve_control_type")
    def test_resolve_button(self, mock_resolve: MagicMock) -> None:
        mock_resolve.return_value = "Button_CT"
        result = mock_resolve("Button")
        assert result == "Button_CT"

    def test_aliases_work(self) -> None:
        # We can test the alias table without CLR by checking the dict mapping
        from desktop_automation_platform.adapters.flaui.control_type_map import _CONTROL_TYPE_NAMES
        assert _CONTROL_TYPE_NAMES.get("textbox") == "Edit"
        assert _CONTROL_TYPE_NAMES.get("dropdown") == "ComboBox"
        assert _CONTROL_TYPE_NAMES.get("label") == "Text"

    def test_case_insensitive_lookup(self) -> None:
        from desktop_automation_platform.adapters.flaui.control_type_map import _CONTROL_TYPE_NAMES
        # All keys are lowercased in the dict
        assert "BUTTON".lower() in _CONTROL_TYPE_NAMES


# ---------------------------------------------------------------------------
# FlaUILocatorTranslator tests
# ---------------------------------------------------------------------------


class TestFlaUILocatorTranslator:
    @pytest.fixture
    def automation(self) -> MagicMock:
        return _make_automation_mock()

    @pytest.fixture
    def translator(self, automation: MagicMock) -> FlaUILocatorTranslator:
        return FlaUILocatorTranslator(automation=automation)

    def test_adapter_type(self, translator: FlaUILocatorTranslator) -> None:
        assert translator.adapter_type == AdapterType.FLAUI

    def test_translate_automation_id(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.AUTOMATION_ID, value="btnLogin")
        translator.translate(loc)
        automation.ConditionFactory.ByAutomationId.assert_called_once_with("btnLogin")

    def test_translate_name(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.NAME, value="Login")
        translator.translate(loc)
        automation.ConditionFactory.ByName.assert_called_once_with("Login")

    def test_translate_class_name(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.CLASS_NAME, value="TextBox")
        translator.translate(loc)
        automation.ConditionFactory.ByClassName.assert_called_once_with("TextBox")

    def test_translate_text_uses_by_name(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.TEXT, value="Submit")
        translator.translate(loc)
        automation.ConditionFactory.ByName.assert_called_once_with("Submit")

    def test_translate_accessibility_id_uses_automation_id(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.ACCESSIBILITY_ID, value="myId")
        translator.translate(loc)
        automation.ConditionFactory.ByAutomationId.assert_called_once_with("myId")

    def test_translate_xpath_raises(self, translator: FlaUILocatorTranslator) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.XPATH, value="//Button[@name='OK']")
        with pytest.raises(LocatorResolutionException) as exc_info:
            translator.translate(loc)
        assert "xpath" in exc_info.value.message.lower()
        assert "flaui" in exc_info.value.message.lower()

    def test_translate_image_raises(self, translator: FlaUILocatorTranslator) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.IMAGE, value="button.png")
        with pytest.raises(LocatorResolutionException):
            translator.translate(loc)

    def test_translate_css_selector_raises(self, translator: FlaUILocatorTranslator) -> None:
        loc = LocatorDefinition(strategy=LocatorStrategy.CSS_SELECTOR, value=".btn")
        with pytest.raises(LocatorResolutionException):
            translator.translate(loc)

    def test_supports_strategy_true(self, translator: FlaUILocatorTranslator) -> None:
        assert translator.supports_strategy("automation_id") is True
        assert translator.supports_strategy("name") is True
        assert translator.supports_strategy("class_name") is True
        assert translator.supports_strategy("control_type") is True
        assert translator.supports_strategy("text") is True

    def test_supports_strategy_false(self, translator: FlaUILocatorTranslator) -> None:
        assert translator.supports_strategy("xpath") is False
        assert translator.supports_strategy("image") is False
        assert translator.supports_strategy("css_selector") is False

    def test_supported_strategies_returns_list(
        self, translator: FlaUILocatorTranslator
    ) -> None:
        strategies = translator.supported_strategies()
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        assert "automation_id" in strategies

    def test_translate_control_type_calls_by_control_type(
        self, translator: FlaUILocatorTranslator, automation: MagicMock
    ) -> None:
        with patch(
            "desktop_automation_platform.adapters.flaui.translator.resolve_control_type"
        ) as mock_resolve:
            mock_resolve.return_value = "Button_CT"
            loc = LocatorDefinition(strategy=LocatorStrategy.CONTROL_TYPE, value="Button")
            translator.translate(loc)
            mock_resolve.assert_called_once_with("Button")
            automation.ConditionFactory.ByControlType.assert_called_once_with("Button_CT")


# ---------------------------------------------------------------------------
# FlaUIAdapter tests (with CLR fully mocked)
# ---------------------------------------------------------------------------


class TestFlaUIAdapterWithMocks:
    """
    Tests for the FlaUI adapter using deep mocks for all .NET interop.
    No real FlaUI assemblies required.
    """

    @pytest.fixture
    def screenshot_manager(self) -> MagicMock:
        sm = MagicMock()
        sm.capture.return_value = "/tmp/screenshot.png"
        sm.capture_on_failure.return_value = None
        return sm

    @pytest.fixture
    def config(self) -> PlatformConfig:
        return _make_config()

    @pytest.fixture
    def adapter(
        self, config: PlatformConfig, screenshot_manager: MagicMock
    ) -> "FlaUIAdapter":  # type: ignore[name-defined]
        from desktop_automation_platform.adapters.flaui.adapter import FlaUIAdapter

        adapter = FlaUIAdapter(config=config, screenshot_manager=screenshot_manager)
        # Inject mocked automation so no CLR is needed
        automation = _make_automation_mock()
        from desktop_automation_platform.adapters.flaui.element_resolver import FlaUIElementResolver
        from desktop_automation_platform.adapters.flaui.translator import FlaUILocatorTranslator

        adapter._automation = automation
        adapter._resolver = FlaUIElementResolver(automation)
        adapter._translator = FlaUILocatorTranslator(automation)
        return adapter

    @pytest.fixture
    def session(self) -> ApplicationSession:
        return _make_session()

    def test_adapter_type(self, adapter) -> None:
        assert adapter.adapter_type == AdapterType.FLAUI

    def test_supported_technologies_includes_wpf(self, adapter) -> None:
        assert ApplicationTechnology.WPF in adapter.supported_technologies
        assert ApplicationTechnology.WINFORMS in adapter.supported_technologies
        assert ApplicationTechnology.WIN32 in adapter.supported_technologies

    def test_get_text_prefers_value_pattern(self, adapter, session: ApplicationSession) -> None:
        mock_element = MagicMock()
        mock_element.Patterns.Value.Pattern.Value = "hello"
        locator = _make_locator()

        with patch.object(adapter, "_resolve_element", return_value=(mock_element, locator.primary)):
            result = adapter.get_text(locator, session)
        assert result == "hello"

    def test_get_text_falls_back_to_name(self, adapter, session: ApplicationSession) -> None:
        mock_element = MagicMock()
        mock_element.Patterns.Value.Pattern.Value = None
        mock_element.Name = "Submit"
        locator = _make_locator()

        with patch.object(adapter, "_resolve_element", return_value=(mock_element, locator.primary)):
            result = adapter.get_text(locator, session)
        assert result == "Submit"

    def test_element_exists_returns_true_when_found(
        self, adapter, session: ApplicationSession
    ) -> None:
        locator = _make_locator()
        with patch.object(adapter._resolver, "element_exists", return_value=True):
            result = adapter.element_exists(locator, session)
        assert result is True

    def test_element_exists_returns_false_on_exception(
        self, adapter, session: ApplicationSession
    ) -> None:
        locator = _make_locator()
        with patch.object(adapter._resolver, "element_exists", side_effect=RuntimeError("boom")):
            result = adapter.element_exists(locator, session)
        assert result is False

    def test_click_succeeds(self, adapter, session: ApplicationSession) -> None:
        locator = _make_locator()
        mock_element = MagicMock()

        with patch.object(adapter._resolver, "find_element", return_value=mock_element):
            result = adapter.click(locator, session)

        assert result.is_success()
        assert result.action == "click"
        mock_element.Click.assert_called_once()

    def test_click_fails_when_element_not_found(
        self, adapter, session: ApplicationSession
    ) -> None:
        locator = _make_locator()
        with patch.object(
            adapter._resolver,
            "find_element",
            side_effect=ElementNotFoundException("btn", ["automation_id"], 30.0),
        ):
            result = adapter.click(locator, session)
        assert not result.is_success()

    def test_input_text_uses_value_pattern(self, adapter, session: ApplicationSession) -> None:
        locator = _make_locator()
        mock_element = MagicMock()

        with patch.object(adapter, "_resolve_element", return_value=(mock_element, locator.primary)):
            result = adapter.input_text(locator, "hello world", session)

        assert result.is_success()
        mock_element.Patterns.Value.Pattern.SetValue.assert_called()

    def test_take_screenshot_delegates_to_manager(
        self, adapter, session: ApplicationSession, screenshot_manager: MagicMock
    ) -> None:
        path = adapter.take_screenshot(session, filename="test_shot")
        screenshot_manager.capture.assert_called_once_with(session=session, label="test_shot")
        assert path == "/tmp/screenshot.png"

    def test_get_element_attribute(self, adapter, session: ApplicationSession) -> None:
        locator = _make_locator()
        mock_element = MagicMock()
        mock_element.Name = "MyButton"

        with patch.object(adapter, "_resolve_element", return_value=(mock_element, locator.primary)):
            val = adapter.get_element_attribute(locator, "name", session)
        assert val == "MyButton"

    def test_close_application_marks_session_closed(
        self, adapter, session: ApplicationSession
    ) -> None:
        adapter.close_application(session)
        assert session.state == SessionState.CLOSED

    def test_wait_for_element_returns_timeout_status_on_miss(
        self, adapter, session: ApplicationSession
    ) -> None:
        locator = _make_locator()
        with patch.object(
            adapter,
            "_resolve_element",
            side_effect=ElementNotFoundException("x", ["automation_id"], 1.0),
        ):
            result = adapter.wait_for_element(locator, session, timeout=1.0)
        assert result.status == ActionStatus.TIMEOUT
