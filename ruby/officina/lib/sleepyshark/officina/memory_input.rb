# frozen_string_literal: true

module Sleepyshark
  module Officina
    # The members of the memory tool's input, as Claude's memory tool names them.
    module MemoryInput
      COMMAND = 'command'
      PATH = 'path'
      OLD_PATH = 'old_path'
      NEW_PATH = 'new_path'
      VIEW_RANGE = 'view_range'
      FILE_TEXT = 'file_text'
      OLD_STR = 'old_str'
      NEW_STR = 'new_str'
      INSERT_LINE = 'insert_line'
      INSERT_TEXT = 'insert_text'
    end
    private_constant :MemoryInput
  end
end
