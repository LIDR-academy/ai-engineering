# ActiveRecord root of the RAG wizard. Persists one transcript → grounded-estimate
# run as it advances stage by stage: each stage writes its FastAPI response into a
# JSONB column, and ``current_step`` tracks which screen the wizard host renders.
#
# Session 10 splits structure from hours. After generation (now structure-only) a
# human reviews the module→task tree (``review``), the hours are derived per task
# by vector search (``hours``), and finally the human edits hours/rates and
# confirms (``verification``). Mirrors the Rag::ChunkingComparison pattern (AR root
# + JSONB + PORO views).
module Rag
  class EstimationRun < ApplicationRecord
    self.table_name = "estimation_runs"

    # Ordered wizard steps. ``transcript`` is the entry form; the rest map to a
    # pipeline stage / human gate and to a JSONB column of the same family.
    # Session 10: the structure is a FREE decomposition of the brief (no retrieval
    # before it); retrieval re-enters per task in the ``hours`` step.
    # Session 12: the hand-written agent now DRIVES those two phases (it proposes
    # the structure in ``generation`` and recovers the ungrounded tasks' hours in
    # ``hours``), around the same human ``review``/``verification`` gates — there is
    # no separate agent step. Its trace rides along in the ``generation`` /
    # ``task_hours`` JSONB.
    STEPS = %w[
      transcript reformulation generation review hours verification
    ].freeze

    # Stage → the JSONB column that must be populated for that step to render.
    STEP_COLUMNS = {
      "reformulation" => :reformulation,
      "generation"    => :generation,          # structure-only (no RAG, no hours)
      "review"        => :structure,           # human-reviewed structure
      "hours"         => :task_hours,          # per-task semantic search (hybrid+rerank)
      "verification"  => :adjusted_breakdown   # confirmed estimate (hours+rate+cost)
    }.freeze

    validates :transcript, presence: true

    scope :recent, -> { order(created_at: :desc) }
    # Session 16 — the review queue (see the migration for why this is a column).
    scope :needs_review, -> { where(requires_human_review: true) }

    # --- typed views over the per-stage JSONB --------------------------------

    def reformulation_view
      Rag::ReformulationView.from_hash(reformulation) if reformulation.present?
    end

    def generation_view
      Rag::GenerationView.from_hash(generation) if generation.present?
    end

    # The human-reviewed structure: modules→tasks WITHOUT hours yet.
    def structure_modules
      Array(structure["modules"]).map { |raw| Rag::WorkModuleView.from_hash(raw) }
    end

    def structure? = structure.present? && structure["modules"].present?

    # The per-task hours estimates (vector search): { "tasks" => [...] }.
    def task_hours_view
      Rag::TaskHoursView.from_hash(task_hours) if task_hours.present?
    end

    # The historical analogs behind each task's hours, indexed by [module, task] so
    # the "hours" step can attach them to the rows it renders from adjusted_modules
    # (which has no "neighbors" attribute of its own). Empty when task_hours is blank;
    # a task with no recorded neighbors maps to an empty array, same as a lookup miss.
    def task_hours_neighbors_by_task
      return {} unless task_hours_view

      task_hours_view.tasks.each_with_object({}) do |task, index|
        index[[ task.module_name, task.task ]] = task.neighbors
      end
    end

    # The human-confirmed breakdown ({ "modules" => [...], "total_hours" => n,
    # "total_cost_eur" => n, "confirmed_at" => iso }). Falsy until saved.
    def adjusted_modules
      Array(adjusted_breakdown["modules"]).map { |raw| Rag::WorkModuleView.from_hash(raw) }
    end

    def adjusted_total_hours = adjusted_breakdown["total_hours"].to_i

    def adjusted_total_cost = adjusted_breakdown["total_cost_eur"].to_i

    def adjusted? = adjusted_breakdown.present? && adjusted_breakdown["modules"].present?

    def confirmed? = adjusted_breakdown["confirmed_at"].present?

    # Session 12: the hand-written agent's reason→act→observe trace, carried inside
    # the phase JSONB it drove. Phase 1 (structure) has a thin one-step trace;
    # phase 2 (hours) has the STEP N recovery trace (empty steps = nothing needed
    # recovery). Nil when the phase was produced by the deterministic path.
    def generation_agent_trace
      raw = generation["agent_trace"] if generation.present?
      Rag::AgentTraceView.from_hash(raw) if raw.present?
    end

    def hours_agent_trace
      raw = task_hours["agent_trace"] if task_hours.present?
      Rag::AgentTraceView.from_hash(raw) if raw.present?
    end

    # Session 16 — mirror the guardrail's verdict out of the task_hours JSONB into
    # its own column, so the listing can find this run. THE only writer: the flag
    # is derived, and derived data with two writers drifts until nobody trusts the
    # badge.
    def sync_review_flag!
      update!(requires_human_review: task_hours_view&.needs_review? || false)
    end

    # --- wizard state --------------------------------------------------------

    def step_complete?(step)
      column = STEP_COLUMNS[step.to_s]
      column ? self[column].present? : true
    end

    # When an earlier stage is re-run, downstream artifacts no longer match the
    # new input — null them so the wizard never shows a stale structure, hours or
    # estimate built from superseded chunks.
    def clear_downstream!(from_step)
      idx = STEPS.index(from_step.to_s)
      return if idx.nil?

      cleared = {}
      STEPS[(idx + 1)..].each do |step|
        column = STEP_COLUMNS[step]
        cleared[column] = {} if column && self.class.column_names.include?(column.to_s)
      end
      # The review flag is derived from task_hours; clearing those without clearing
      # it would leave a badge pointing at hours that no longer exist.
      cleared[:requires_human_review] = false if cleared.key?(:task_hours)
      update!(cleared) if cleared.any?
    end
  end
end
