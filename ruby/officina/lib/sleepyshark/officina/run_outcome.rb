# frozen_string_literal: true

module Sleepyshark
  module Officina
    # How a run ended, in the word its span, metrics and audit trail give it.
    module RunOutcome
      # @param result [Completed, Stopped, Failed, nil] nil when the host left the run
      def self.of(result)
        case result
        in Completed then 'completed'
        in Stopped then 'stopped'
        in Failed then 'failed'
        in nil then 'abandoned'
        end
      end
    end
    private_constant :RunOutcome
  end
end
