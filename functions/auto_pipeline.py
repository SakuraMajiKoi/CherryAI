"""Automatic Pipeline Orchestrator for CherryAI (Phase 58.4).

Purpose:
- Execute the 8-step pipeline automatically after file loading
- Support configurable pipeline levels (0-4)
- Integrate with ManifestManager for state persistence

Pipeline Steps:
1. Create Manifest (Project Name Dialog) - already happens in GUI
2. Load Lines (extract from files) - happens in input step
3. Load Defaults (apply defaults.ini)
4. Run Analysis (functions/analysis.py)
5. Populate Inferences (optional, based on settings)
6. Run Original Estimation
7. Run Default Preprocessing
8. Run Preprocessed Estimation

Pipeline Levels:
0: Manual - No automatic execution
1: Analyze - Steps 1-4 (create, load, defaults, analyze)
2: Estimate Original - Steps 1-6 (+ inference, original estimation)
3: Preprocess - Steps 1-7 (+ default preprocessing)
4: Mock Translate - Steps 1-8 (+ preprocessed estimation)

Module Authorship: Claude (Phase 58.4)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .manifest_manager import ManifestManager, Manifest

logger = logging.getLogger(__name__)


class PipelineLevel(IntEnum):
    """Pipeline execution levels.

    Higher levels include all steps from lower levels.
    """

    MANUAL = 0  # No automatic execution
    ANALYZE = 1  # Steps 1-4
    ESTIMATE_ORIGINAL = 2  # Steps 1-6 (+ inference, original estimation)
    PREPROCESS = 3  # Steps 1-7 (+ preprocessing)
    MOCK_TRANSLATE = 4  # Steps 1-8 (+ preprocessed estimation)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    success: bool
    level: PipelineLevel
    steps_completed: List[str] = field(default_factory=list)
    error_step: Optional[str] = None
    error_message: Optional[str] = None
    analysis_results: Optional[Dict[str, Any]] = None
    original_estimation: Optional[Dict[str, Any]] = None
    preprocessed_estimation: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None  # PHASE 58.6
    execution_time_ms: int = 0  # PHASE 58.8


@dataclass
class PipelineContext:
    """Context for pipeline execution."""

    manifest_manager: "ManifestManager"
    project_dir: Optional[Path] = None
    input_files: List[Path] = field(default_factory=list)
    encoding: str = "auto"
    format_filter: str = "auto"

    # Callbacks for GUI integration
    on_step_start: Optional[Callable[[str], None]] = None
    on_step_complete: Optional[Callable[[str, bool], None]] = None
    on_progress: Optional[Callable[[str, float], None]] = None

    # Inference options (Phase 58.5)
    infer_speakers_to_glossary: bool = False
    infer_codes_to_database: bool = False
    infer_pov: bool = False
    infer_gender: bool = False


class AutoPipeline:
    """Automatic pipeline orchestrator.

    Executes the 8-step pipeline based on configured level.
    Designed to be called from GUI or CLI contexts.
    """

    def __init__(self, context: PipelineContext) -> None:
        """Initialize the pipeline.

        Args:
            context: Pipeline execution context.
        """
        self._context = context
        self._result = PipelineResult(success=True, level=PipelineLevel.MANUAL)
        self._start_time: float = 0

    def execute(self, level: PipelineLevel) -> PipelineResult:
        """Execute the pipeline up to the specified level.

        Args:
            level: Target pipeline level.

        Returns:
            PipelineResult with execution status.
        """
        self._result.level = level
        self._start_time = time.perf_counter()

        if level < PipelineLevel.ANALYZE:
            return self._finalize_result()

        try:
            # Level 1+: Steps 1-4
            self._step_load_defaults()
            self._step_run_analysis()

            if level < PipelineLevel.ESTIMATE_ORIGINAL:
                return self._finalize_result()

            # Level 2+: Steps 5-6
            self._step_populate_inferences()
            self._step_estimate_original()

            if level < PipelineLevel.PREPROCESS:
                return self._finalize_result()

            # Level 3+: Step 7
            self._step_run_preprocessing()

            if level < PipelineLevel.MOCK_TRANSLATE:
                return self._finalize_result()

            # Level 4: Steps 8-12 (Mock Translation)
            self._step_estimate_preprocessed()
            self._step_mock_translation()
            self._step_run_qa_validation()
            self._step_run_postprocessing()
            self._step_generate_summary()

        except PipelineError as e:
            self._result.success = False
            self._result.error_step = e.step
            self._result.error_message = str(e)
            logger.error("Pipeline failed at step '%s': %s", e.step, e)

        return self._finalize_result()

    def _finalize_result(self) -> PipelineResult:
        """Finalize pipeline result with timing and record to manifest.

        PHASE 58.8: Records pipeline execution details in manifest.
        """
        # Calculate execution time
        elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
        self._result.execution_time_ms = elapsed_ms

        # Record to manifest
        self._record_to_manifest()

        return self._result

    def _record_to_manifest(self) -> None:
        """Record pipeline execution in manifest (PHASE 58.8)."""
        mm = self._context.manifest_manager
        manifest = mm.current if mm else None

        if manifest is None:
            return

        # Prepare execution record
        execution_record = {
            "level": self._result.level.value,
            "level_name": self._result.level.name,
            "steps_completed": self._result.steps_completed.copy(),
            "execution_time_ms": self._result.execution_time_ms,
            "success": self._result.success,
        }

        if self._result.error_step:
            execution_record["error_step"] = self._result.error_step
            execution_record["error_message"] = self._result.error_message

        # Store in manifest step_state
        if not hasattr(manifest, "step_state"):
            manifest.step_state = {}
        if "Input" not in manifest.step_state:
            manifest.step_state["Input"] = {}

        manifest.step_state["Input"]["pipeline_executed"] = execution_record

        logger.info(
            "Recorded pipeline execution: level=%s, steps=%d, time=%dms",
            self._result.level.name,
            len(self._result.steps_completed),
            self._result.execution_time_ms,
        )

    def _notify_start(self, step: str) -> None:
        """Notify that a step is starting."""
        logger.info("Pipeline step starting: %s", step)
        if self._context.on_step_start:
            self._context.on_step_start(step)

    def _notify_complete(self, step: str, success: bool = True) -> None:
        """Notify that a step is complete."""
        if success:
            self._result.steps_completed.append(step)
        logger.info("Pipeline step complete: %s (success=%s)", step, success)
        if self._context.on_step_complete:
            self._context.on_step_complete(step, success)

    def _step_load_defaults(self) -> None:
        """Step 3: Load defaults from defaults.ini."""
        step_name = "load_defaults"
        self._notify_start(step_name)

        try:
            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping defaults")
                self._notify_complete(step_name, True)
                return

            # Apply defaults from embedded factory defaults (Session 25: removed config/defaults.ini)
            from .ini_manager import get_all_initial_defaults
            defaults = get_all_initial_defaults()
            if defaults:
                self._apply_defaults_from_dict(manifest, defaults)
                logger.info("Applied embedded factory defaults to manifest")

            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _apply_defaults_from_dict(
        self, manifest: "Manifest", defaults: Dict[str, Any]
    ) -> None:
        """Apply settings from a defaults dict to manifest.

        Args:
            manifest: Manifest to update.
            defaults: Dict of default key/value pairs.
        """
        # Update manifest settings if not already set
        if hasattr(manifest, "settings"):
            for key, value in defaults.items():
                if not getattr(manifest.settings, key, None):
                    if hasattr(manifest.settings, key):
                        setattr(manifest.settings, key, value)

    def _apply_defaults_from_ini(
        self, manifest: "Manifest", defaults_path: Path
    ) -> None:
        """Apply settings from defaults.ini to manifest (legacy — kept for compat).

        Args:
            manifest: Manifest to update.
            defaults_path: Path to defaults.ini file.
        """
        import configparser

        config = configparser.ConfigParser()
        config.read(defaults_path, encoding="utf-8")

        # Apply relevant defaults to manifest
        if config.has_section("DEFAULT"):
            defaults = dict(config["DEFAULT"])
            # Update manifest settings if not already set
            if hasattr(manifest, "settings"):
                for key, value in defaults.items():
                    if not getattr(manifest.settings, key, None):
                        if hasattr(manifest.settings, key):
                            setattr(manifest.settings, key, value)

    def _step_run_analysis(self) -> None:
        """Step 4: Run analysis on input files."""
        step_name = "run_analysis"
        self._notify_start(step_name)

        try:
            from .analysis import analyze_manifest

            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping analysis")
                self._notify_complete(step_name, True)
                return

            # Run analysis and store results
            analysis_results = analyze_manifest(manifest)
            self._result.analysis_results = analysis_results

            # Store in manifest
            if hasattr(manifest, "analysis"):
                manifest.analysis = analysis_results

            self._notify_complete(step_name, True)

        except ImportError:
            # analyze_manifest may not exist, try file-based analysis
            logger.warning("analyze_manifest not available, using file-based")
            self._run_file_based_analysis()
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _run_file_based_analysis(self) -> None:
        """Run analysis on individual files."""
        from .analysis import analyze_file

        mm = self._context.manifest_manager
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        combined_results: Dict[str, Any] = {}

        for file_path in self._context.input_files:
            if file_path.exists():
                try:
                    result = analyze_file(file_path, logs_dir)
                    combined_results[str(file_path)] = result
                except Exception as e:
                    logger.warning("Analysis failed for %s: %s", file_path, e)

        self._result.analysis_results = combined_results

    def _step_populate_inferences(self) -> None:
        """Step 5: Populate inferences from analysis results."""
        step_name = "populate_inferences"
        self._notify_start(step_name)

        try:
            if not any([
                self._context.infer_speakers_to_glossary,
                self._context.infer_codes_to_database,
                self._context.infer_pov,
                self._context.infer_gender,
            ]):
                logger.debug("No inference options enabled, skipping")
                self._notify_complete(step_name, True)
                return

            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping inferences")
                self._notify_complete(step_name, True)
                return

            analysis = self._result.analysis_results or {}

            # Phase 58.5: Inference population
            if self._context.infer_speakers_to_glossary:
                self._infer_speakers_to_glossary(manifest, analysis)

            if self._context.infer_codes_to_database:
                self._infer_codes_to_database(manifest, analysis)

            if self._context.infer_pov:
                self._infer_pov(manifest, analysis)

            # Gender inference requires LLM, defer to Phase 59
            if self._context.infer_gender:
                logger.debug("Gender inference requires LLM, deferring")

            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _infer_speakers_to_glossary(
        self, manifest: "Manifest", analysis: Dict[str, Any]
    ) -> None:
        """Add detected speakers to glossary.

        Args:
            manifest: Manifest to update.
            analysis: Analysis results.
        """
        speakers = analysis.get("detected_speakers", [])
        if not speakers:
            # Try getting from nested file results
            for file_result in analysis.values():
                if isinstance(file_result, dict):
                    speakers.extend(file_result.get("detected_speakers", []))

        if not speakers:
            logger.debug("No speakers detected to add to glossary")
            return

        logger.info("Adding %d detected speakers to glossary", len(speakers))

        # Add to manifest glossary
        if not hasattr(manifest, "glossary"):
            manifest.glossary = []

        existing = {entry.get("source", "") for entry in manifest.glossary}

        for speaker in speakers:
            if speaker not in existing:
                manifest.glossary.append({
                    "source": speaker,
                    "target": speaker,  # Keep original for now
                    "type": "name",
                    "inferred": True,
                })

    def _infer_codes_to_database(
        self, manifest: "Manifest", analysis: Dict[str, Any]
    ) -> None:
        """Add detected code patterns to code glossary.

        Args:
            manifest: Manifest to update.
            analysis: Analysis results.
        """
        code_patterns = analysis.get("detected_codes", [])
        if not code_patterns:
            for file_result in analysis.values():
                if isinstance(file_result, dict):
                    code_patterns.extend(file_result.get("detected_codes", []))

        if not code_patterns:
            logger.debug("No code patterns detected to add to database")
            return

        logger.info("Adding %d code patterns to code glossary", len(code_patterns))

        if not hasattr(manifest, "code_glossary"):
            manifest.code_glossary = []

        existing = {entry.get("pattern", "") for entry in manifest.code_glossary}

        for pattern in code_patterns:
            if pattern not in existing:
                manifest.code_glossary.append({
                    "pattern": pattern,
                    "inferred": True,
                })

    def _infer_pov(
        self, manifest: "Manifest", analysis: Dict[str, Any]
    ) -> None:
        """Infer point of view from analysis.

        Args:
            manifest: Manifest to update.
            analysis: Analysis results.
        """
        pov = analysis.get("detected_pov")
        if not pov:
            for file_result in analysis.values():
                if isinstance(file_result, dict) and file_result.get("detected_pov"):
                    pov = file_result["detected_pov"]
                    break

        if pov and hasattr(manifest, "options"):
            logger.info("Setting inferred POV: %s", pov)
            manifest.options.pov = pov

    def _step_estimate_original(self) -> None:
        """Step 6: Estimation placeholder (handled by Costs GUI step)."""
        self._notify_start("estimate_original")
        self._notify_complete("estimate_original", True)

    def _step_run_preprocessing(self) -> None:
        """Step 7: Run default preprocessing."""
        step_name = "run_preprocessing"
        self._notify_start(step_name)

        try:
            from CherryAI.gui.helpers.mode_adapter import apply_preprocessing

            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping preprocessing")
                self._notify_complete(step_name, True)
                return

            lines = getattr(manifest, "lines", [])
            if not lines:
                logger.debug("No lines to preprocess")
                self._notify_complete(step_name, True)
                return

            # Build config from manifest options and run preprocessing
            config = self._build_preprocessing_config(manifest)
            source_lines = [getattr(line, "text", "") for line in lines]
            processed_lines, stats = apply_preprocessing(source_lines, config)

            for line, processed in zip(lines, processed_lines):
                if hasattr(line, "prepro"):
                    line.prepro = processed
                else:
                    setattr(line, "prepro", processed)

            manifest.preprocessed_lines = processed_lines
            manifest.preprocessing_stats = stats

            self._notify_complete(step_name, True)

        except ImportError as e:
            # Try alternative preprocessing approach
            self._run_basic_preprocessing()
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _run_basic_preprocessing(self) -> None:
        """Run basic preprocessing without full preprocessing module."""
        logger.info("Running basic preprocessing")

        # Basic preprocessing steps that can be done without full module:
        # - Trim whitespace
        # - Normalize line endings
        # - Remove empty lines option

        mm = self._context.manifest_manager
        manifest = mm.current

        if manifest is None or not hasattr(manifest, "lines"):
            return

        for line in manifest.lines:
            if hasattr(line, "text"):
                # Basic trimming
                line.text = line.text.strip()

    def _build_preprocessing_config(self, manifest: "Manifest") -> Dict[str, Any]:
        """Build preprocessing configuration from manifest options."""
        options = (
            manifest.get_preprocessing_options()
            if hasattr(manifest, "get_preprocessing_options")
            else {}
        )

        src_lang = "ja"
        tgt_lang = "en"
        if hasattr(manifest, "get_project_info"):
            info = manifest.get_project_info()
            src_lang = getattr(info, "source_language", src_lang)
            tgt_lang = getattr(info, "target_language", tgt_lang)

        return {
            "ellipsis_enabled": options.get("EllipsisCompression", True),
            "symbol_conversion_enabled": options.get("SymbolConversion", True),
            "symbol_src_lang": src_lang,
            "symbol_tgt_lang": tgt_lang,
            "prot_compression_enabled": options.get("ProtCompression", True),
            "protect_code_patterns": options.get("ProtectCodePatterns", []),
            "placeholder_rules": options.get("CustomPlaceholders", []),
        }

    def _step_estimate_preprocessed(self) -> None:
        """Step 8: Estimation placeholder (handled by Costs GUI step)."""
        self._notify_start("estimate_preprocessed")
        self._notify_complete("estimate_preprocessed", True)

    def _step_mock_translation(self) -> None:
        """Step 9: Run mock translation (no API calls).

        PHASE 58.6: Mock translation for pipeline level 4.
        """
        step_name = "mock_translation"
        self._notify_start(step_name)

        try:
            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping mock translation")
                self._notify_complete(step_name, True)
                return

            # Get lines to translate
            lines = getattr(manifest, "preprocessed_lines", None)
            if lines is None:
                lines = getattr(manifest, "lines", [])

            if not lines:
                logger.debug("No lines to translate")
                self._notify_complete(step_name, True)
                return

            # Perform mock translation (copy source to target)
            for line in lines:
                if hasattr(line, "source") and hasattr(line, "target"):
                    if not line.target:  # Only if not already translated
                        line.target = line.source
                elif hasattr(line, "text"):
                    # Single-column format
                    if not hasattr(line, "translation"):
                        line.translation = line.text

            logger.info("Mock translation completed for %d lines", len(lines))
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _step_run_qa_validation(self) -> None:
        """Step 10: Run QA validation on translations.

        PHASE 58.6: Validate mock translations.
        """
        step_name = "qa_validation"
        self._notify_start(step_name)

        try:
            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping QA validation")
                self._notify_complete(step_name, True)
                return

            # Basic QA validation
            issues: List[Dict[str, Any]] = []

            lines = getattr(manifest, "lines", [])
            for i, line in enumerate(lines):
                source = getattr(line, "source", "") or getattr(line, "text", "")
                target = getattr(line, "target", "") or getattr(line, "translation", "")

                # Check for empty translations
                if source and not target:
                    issues.append({
                        "line": i,
                        "type": "empty_translation",
                        "message": "Empty translation",
                    })

                # Check for identical source/target (may be intentional)
                if source == target and source:
                    issues.append({
                        "line": i,
                        "type": "identical",
                        "message": "Source and target are identical",
                        "severity": "info",
                    })

            # Store QA results
            if hasattr(manifest, "qa_results"):
                manifest.qa_results = issues
            elif hasattr(manifest, "__dict__"):
                manifest.qa_results = issues

            logger.info("QA validation found %d issues", len(issues))
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _step_run_postprocessing(self) -> None:
        """Step 11: Run postprocessing on translations.

        PHASE 58.6: Apply postprocessing modi.
        """
        step_name = "postprocessing"
        self._notify_start(step_name)

        try:
            from .postprocess import postprocess_manifest

            mm = self._context.manifest_manager
            manifest = mm.current

            if manifest is None:
                logger.warning("No manifest loaded, skipping postprocessing")
                self._notify_complete(step_name, True)
                return

            postprocess_manifest(manifest)
            self._notify_complete(step_name, True)

        except ImportError:
            logger.info("Postprocessing module not available, skipping")
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e

    def _step_generate_summary(self) -> None:
        """Step 12: Generate pipeline execution summary.

        PHASE 58.6: Summary display after mock translation.
        """
        step_name = "generate_summary"
        self._notify_start(step_name)

        try:
            mm = self._context.manifest_manager
            manifest = mm.current

            summary = {
                "pipeline_level": self._result.level.name,
                "steps_completed": len(self._result.steps_completed),
                "success": self._result.success,
            }

            if manifest is not None:
                lines = getattr(manifest, "lines", [])
                summary["total_lines"] = len(lines)

                # Count translated
                translated = 0
                for line in lines:
                    target = getattr(line, "target", None) or getattr(line, "translation", None)
                    if target:
                        translated += 1
                summary["translated_lines"] = translated

            # Store summary
            self._result.summary = summary
            logger.info("Pipeline summary: %s", summary)
            self._notify_complete(step_name, True)

        except Exception as e:
            raise PipelineError(step_name, str(e)) from e


class PipelineError(Exception):
    """Exception raised when a pipeline step fails."""

    def __init__(self, step: str, message: str) -> None:
        """Initialize the error.

        Args:
            step: Name of the step that failed.
            message: Error message.
        """
        self.step = step
        super().__init__(f"Pipeline step '{step}' failed: {message}")


def run_auto_pipeline(
    manifest_manager: "ManifestManager",
    level: int = 3,
    input_files: Optional[List[Path]] = None,
    **kwargs: Any,
) -> PipelineResult:
    """Convenience function to run the automatic pipeline.

    Args:
        manifest_manager: ManifestManager instance.
        level: Pipeline level (0-4).
        input_files: Optional list of input files.
        **kwargs: Additional context options.

    Returns:
        PipelineResult with execution status.
    """
    context = PipelineContext(
        manifest_manager=manifest_manager,
        input_files=input_files or [],
        **kwargs,
    )

    pipeline = AutoPipeline(context)
    return pipeline.execute(PipelineLevel(level))


def get_pipeline_level_description(level: int) -> str:
    """Get human-readable description for a pipeline level.

    Args:
        level: Pipeline level (0-4).

    Returns:
        Description string.
    """
    descriptions = {
        0: "Manual - No automatic execution",
        1: "Analyze - Create manifest, load, analyze",
        2: "Estimate Original - Analyze + inference + original estimation",
        3: "Preprocess - Estimate + default preprocessing",
        4: "Mock Translate - Full pipeline including mock translation",
    }
    return descriptions.get(level, f"Unknown level {level}")
