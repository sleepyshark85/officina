# frozen_string_literal: true

require 'json'

module Sleepyshark
  module Officina
    # Memory as a tool: the commands of Claude's memory tool (view, create, str_replace, insert, delete, rename) over
    # files under /memories, kept in a memory store under the run's memory scope, which the run names. It is a write
    # tool, so each call runs alone and, when the agent has an audit sink, only once its attempt is in the trail; with
    # +needs_approval+, the commands that change memory need approval, and views never do. The model reads memory when
    # it needs it: memory is never in the instructions. A provider with a memory tool of its own, which its model is
    # trained on, sends that in its place.
    #
    # @example
    #   agent = Agent.new(model:, instructions:, tools: [MemoryTool.new(FileMemoryStore.new('memory'))])
    #   agent.run(conversation, 'I prefer prices with tax.', memory_scope: 'sam')
    class MemoryTool < Tool
      # The memory directory as the model sees it.
      ROOT = '/memories'
      # What a provider without a memory tool of its own would send. Both are part of the prefix, written as .NET
      # writes them, so an agent with memory has the same fingerprint in every implementation.
      DESCRIPTION = "Your memory: a directory of text files under #{ROOT} that persists across conversations. " \
                    "Commands: view (a file, or a directory's listing), create (create or overwrite a file), " \
                    'str_replace, insert, delete and rename.'.freeze
      SCHEMA = Schema.new(<<~JSON.chomp)
        {"type":"object","properties":{"command":{"type":"string","enum":["view","create","str_replace","insert","delete","rename"]},
        "path":{"type":"string"},"view_range":{"type":"array","items":{"type":"integer"}},"file_text":{"type":"string"},
        "old_str":{"type":"string"},"new_str":{"type":"string"},"insert_line":{"type":"integer"},"insert_text":{"type":"string"},
        "old_path":{"type":"string"},"new_path":{"type":"string"}},"required":["command"]}
      JSON
      # What starts every path under the memory directory.
      UNDER_ROOT = "#{ROOT}/".freeze
      private_constant :DESCRIPTION, :SCHEMA, :UNDER_ROOT

      # @param store [_MemoryStore] where the files are kept; one store may serve many agents and runs
      # @param needs_approval [Boolean] whether the agent's approver must approve each command that changes memory
      def initialize(store, needs_approval: false)
        # A lambda, not a block: Steep 2.1 crashes on a block given to super with arguments and skips the file.
        handler = ->(input, _cancel, scope) { command(store, scope, input) }
        super(name: 'memory', description: DESCRIPTION, input: SCHEMA, kind: :write, needs_approval:, &handler)
      end

      def memory? = true

      # A view only reads, so it never needs approval.
      def needs_approval_for?(input) = super && !(command_of(JSON.parse(input)) in :view)

      private

      # Runs the call's command, unless a path it names is not under the memory directory.
      # @raise [Error] when there is no memory scope: the tool was called outside a run
      def command(store, scope, input)
        raise Error, 'The memory tool needs the memory scope of a run' unless scope

        name = command_of(input)
        named = paths_of(name, input)
        # @type var scoped: Hash[String, String]
        scoped = {}
        named.each do |path|
          at = within(path)
          return outside(path) unless at

          scoped[path] = at
        end
        MemoryCommand.new(MemoryFiles.new(store, scope), input, named, scoped).run(name)
      end

      # The paths the command names: a rename's old and new ones, else its one.
      def paths_of(name, input)
        return [input[MemoryInput::PATH]] unless name == :rename

        input.values_at(MemoryInput::OLD_PATH, MemoryInput::NEW_PATH)
      end

      # The input's command, as a Symbol.
      def command_of(input) = input.fetch(MemoryInput::COMMAND).to_sym

      def outside(path)
        ToolFailure.new(message: "Error: The path #{path || '(none)'} is not a valid path under #{ROOT}.")
      end

      # The path within the scope that the model's path names: empty for the memory directory, nil for none.
      def within(path)
        path = path&.delete_suffix('/')
        return '' if path == ROOT

        return unless path&.start_with?(UNDER_ROOT)

        rest = path.delete_prefix(UNDER_ROOT)
        rest if MemoryRules.valid_path?(rest)
      end
    end
  end
end
