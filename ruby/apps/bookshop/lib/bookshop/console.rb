# frozen_string_literal: true

module Bookshop
  # The staff member's console: asks who is using it, then reads messages and commands, streams each reply with its
  # tool activity, asks approval for changes, and cancels the reply in progress on Ctrl+C, after which the session
  # goes on; Ctrl+C with no reply in progress leaves. Each conversation is a session, saved after every step of a
  # reply; each reply ends with a status line of its tokens and cost, and stops at its own or its session's budget.
  # Each reply is traced and logged; /audit shows a session's audit trail. Each staff member has their own memory,
  # which /memory shows.
  class Console
    Command = Data.define(:name, :argument, :help, :handler)

    # One command: its name, the argument it takes (nil for none) as its help line shows it, and the private method
    # that answers it, given the argument and the session in use, and returning the session to go on with.
    class Command
      # The command as its help line names it, such as "/resume <id>".
      def usage = [name, *argument].join(' ')
    end

    # The command the hint at the start and after an unknown command names.
    HELP_COMMAND = Command.new('/help', nil, 'Show this help.', :help)
    # The commands, by name, in the order the help lists them.
    COMMANDS = [
      HELP_COMMAND,
      Command.new('/new', nil, 'Start a new session.', :start_new),
      Command.new('/sessions', nil, 'List the latest sessions.', :list_sessions),
      Command.new('/resume', '<id>', 'Go on with the session with that id.', :resume),
      Command.new('/cost', nil, "Show this session's tokens and cost.", :cost),
      Command.new('/audit', '[<id>]', 'Show the audit trail of this session, or of the session with that id.', :audit),
      Command.new('/memory', nil, 'Show what the assistant remembers for you.', :memory),
      Command.new('/quit', nil, 'Leave the assistant.', :quit)
    ].to_h { [it.name, it] }.freeze
    # What starts a command, rather than a message.
    COMMAND_START = '/'
    HELP_HINT = "Type #{HELP_COMMAND.name} for commands.".freeze
    # Each command's help line, its usage padded to line the help lines up two spaces after the longest.
    USAGE_WIDTH = COMMANDS.values.map { it.usage.length }.max + 2
    HELP = ['Commands:', *COMMANDS.values.map { "  #{it.usage.ljust(USAGE_WIDTH)}#{it.help}" },
            'Anything else is a message to the assistant. Ctrl+C stops a reply in progress.'].join("\n").freeze
    private_constant :Command, :HELP_COMMAND, :COMMANDS, :COMMAND_START, :HELP_HINT, :USAGE_WIDTH, :HELP

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

    # Converses until /quit or the end of the input, and returns the session in use then.
    def converse(session)
      catch(:quit) do
        while (line = @terminal.read('you> '))
          text = line.strip
          if text.start_with?(COMMAND_START) then session = command(text, session)
          elsif !text.empty? then reply(session, line)
          end
        end
      end
      session
    end

    # Answers the command line, and returns the session to go on with; /quit throws :quit. A command that takes no
    # argument is unknown with one.
    def command(line, session)
      name, argument = line.split(/\s+/, 2)
      argument = argument.to_s
      command = COMMANDS[name]
      return method(command.handler).call(argument, session) if command && (command.argument || argument.empty?)

      @terminal.write_line("Unknown command #{line}. #{HELP_HINT}")
      session
    end

    def help(_argument, session) = answered(session) { @terminal.write_line(HELP) }
    def start_new(_argument, session) = @sessions.start_new(session)
    def list_sessions(_argument, session) = answered(session) { @sessions.list(session) }
    def resume(id, session) = @sessions.resume(id, session)
    def cost(_argument, session) = answered(session) { @sessions.cost(session) }
    def memory(_argument, session) = answered(session) { @terminal.write_line(@memory.show(session.staff_member)) }
    def quit(_argument, _session) = throw(:quit)

    # Shows the audit trail of the session with the id, the session in use's if it names none.
    def audit(id, session)
      answered(session) { @terminal.write_line(@audit.show(id.empty? ? session.id : id)) }
    end

    # Runs the block, which answers a command that goes on with the session in use, and returns that session.
    def answered(session)
      yield
      session
    end

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
