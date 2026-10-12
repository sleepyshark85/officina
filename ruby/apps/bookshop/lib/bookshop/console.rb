# frozen_string_literal: true

module Bookshop
  # The staff member's console: asks who is using it, then reads messages and commands, streams each reply with its
  # tool activity, asks approval for changes, and cancels the reply in progress on Ctrl+C, after which the session
  # goes on; Ctrl+C with no reply in progress leaves. Each conversation is a session, saved after every step of a
  # reply; each reply ends with a status line of its tokens and cost, and stops at its own or its session's budget.
  # Each reply is traced and logged; /audit shows a session's audit trail. Each staff member has their own memory,
  # which /memory shows.
  class Console
    Command = Data.define(:name, :argument, :help)

    # One command: its name, and the argument it takes (nil for none) and what it does, as its help line shows them.
    class Command
      # The command as its help line names it, such as "/resume <id>".
      def usage = [name, *argument].join(' ')

      # Whether the word is this command's name, so that a command matches its name in a pattern.
      def ===(other) = name == other
    end

    HELP_COMMAND = Command.new('/help', nil, 'Show this help.')
    NEW = Command.new('/new', nil, 'Start a new session.')
    SESSIONS = Command.new('/sessions', nil, 'List the latest sessions.')
    RESUME = Command.new('/resume', '<id>', 'Go on with the session with that id.')
    COST = Command.new('/cost', nil, "Show this session's tokens and cost.")
    AUDIT = Command.new('/audit', '[<id>]', 'Show the audit trail of this session, or of the session with that id.')
    MEMORY = Command.new('/memory', nil, 'Show what the assistant remembers for you.')
    QUIT = Command.new('/quit', nil, 'Leave the assistant.')
    # The commands in the order the help lists them.
    COMMANDS = [HELP_COMMAND, NEW, SESSIONS, RESUME, COST, AUDIT, MEMORY, QUIT].freeze
    # What starts a command, rather than a message.
    COMMAND_START = '/'
    HELP_HINT = "Type #{HELP_COMMAND.name} for commands.".freeze
    # Each command's help line, its usage padded to line the help lines up two spaces after the longest.
    USAGE_WIDTH = COMMANDS.map { it.usage.length }.max + 2
    HELP = ['Commands:', *COMMANDS.map { "  #{it.usage.ljust(USAGE_WIDTH)}#{it.help}" },
            'Anything else is a message to the assistant. Ctrl+C stops a reply in progress.'].join("\n").freeze
    private_constant :Command, :HELP_COMMAND, :NEW, :SESSIONS, :RESUME, :COST, :AUDIT, :MEMORY, :QUIT, :COMMANDS,
                     :COMMAND_START, :HELP_HINT, :USAGE_WIDTH, :HELP

    # @param agent [Sleepyshark::Officina::Agent] the chat agent, whose approver is +approvals+
    # @param approvals [Approvals]
    # @param input [IO] the staff member's lines
    # @param output [IO]
    # @param clock [#call] returns the current Time, for the run context
    # @param store [SessionStore] where the sessions are kept
    # @param budgets [Budgets]
    # @param audit [AuditView] what /audit shows
    # @param memory [StaffMemory] what /memory shows
    # @param telemetry [Telemetry] which traces and logs each reply
    # @param summarizer [Summarizer, nil] which summarizes each session left; nil for none
    # @param demo [Boolean] whether to say at the start that the agent compacts and clears early (ChatAgent.mode)
    def initialize(agent:, approvals:, input:, output:, clock:, store:, budgets:, audit:, memory:, telemetry:,
                   summarizer:, demo:)
      @demo = demo
      @audit = audit
      @memory = memory
      @telemetry = telemetry
      @approvals = approvals
      @budgets = budgets
      @terminal = Terminal.new(input:, output:)
      @sessions = SessionCommands.new(agent:, store:, clock:, budgets:, terminal: @terminal, summarizer:, telemetry:)
      # Ending the input ends the session, as its end does.
      @interrupts = Interrupts.new(idle: -> { @terminal.end_input })
    end

    # Runs until /quit or the end of the input, and summarizes each session it leaves: with /new, /resume, /quit or
    # the end of the input.
    def run
      @interrupts.watch do
        @terminal.write_line("Bookshop Assistant. #{HELP_HINT}")
        @terminal.write_line(ChatAgent.demo_announcement) if @demo
        staff_member = ask_staff_member
        @sessions.leave(converse(@sessions.start(staff_member))) if staff_member
      end
    ensure
      @terminal.close
    end

    private

    # The staff member's name, asked until one that can name their memory is given; nil at the end of the input.
    def ask_staff_member
      while (line = @terminal.read('Who is using the assistant? Your name: '))
        name = line.strip
        next if name.empty?

        if StaffMemory.valid_name?(name)
          @terminal.write_line("Hello, #{name}.")
          return name
        end
        @terminal.write_line('That name cannot be used. Please give another name.')
      end
    end

    # Converses until /quit or the end of the input, and returns the session in use then. A command that takes no
    # argument is unknown with one; /audit with no id shows the session in use's trail.
    # One branch per command: a flat dispatch reads better than one split across methods at an arbitrary branch.
    # rubocop:disable Metrics/AbcSize, Metrics/CyclomaticComplexity -- one branch per command, as said above
    # rubocop:disable Metrics/MethodLength, Metrics/PerceivedComplexity -- one branch per command, as said above
    def converse(session)
      while (line = @terminal.read('you> '))
        name, argument = line.strip.split(/\s+/, 2)
        case [name, argument]
        in [nil, nil] then next
        in [QUIT, nil] then return session
        in [NEW, nil] then session = @sessions.start_new(session)
        in [RESUME, id] then session = @sessions.resume(id.to_s, session)
        in [SESSIONS, nil] then @sessions.list(session)
        in [COST, nil] then @sessions.cost(session)
        in [AUDIT, id] then @terminal.write_line(@audit.show(id || session.id))
        in [MEMORY, nil] then @terminal.write_line(@memory.show(session.staff_member))
        in [HELP_COMMAND, nil] then @terminal.write_line(HELP)
        in [String => word, _] if word.start_with?(COMMAND_START)
          @terminal.write_line("Unknown command #{line.strip}. #{HELP_HINT}")
        else reply(session, line)
        end
      end
      session
    end
    # rubocop:enable Metrics/AbcSize, Metrics/CyclomaticComplexity, Metrics/MethodLength, Metrics/PerceivedComplexity

    def reply(session, message)
      cancel = Sleepyshark::Officina::Cancellation.new
      view = ReplyView.new(terminal: @terminal, approvals: @approvals, cancel:,
                           budget_reached: @budgets.reached(session.cost))
      budget = @budgets.for_reply(session.cost)
      result = @telemetry.reply(session.id) do
        @interrupts.cancelling(cancel) { session.reply(message, cancel:, budget:) { |event| view.show(event) } }
      end
      view.finish(result, session_cost: session.cost)
    ensure
      # The run has ended, so nothing waits for an answer.
      @approvals.clear
    end
  end
  private_constant :Console
end
