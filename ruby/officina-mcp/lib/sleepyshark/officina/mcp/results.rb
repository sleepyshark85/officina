# frozen_string_literal: true

module Sleepyshark
  module Officina
    module Mcp
      # What the results of tools/list and tools/call hold. JSON.parse makes each value an instance of the class
      # itself, never of a subclass, so each is checked with instance_of?, and each member is read once (values_at).
      module Results
        # The members of the results this module reads, as the protocol names them.
        TOOLS = 'tools'
        NEXT_CURSOR = 'nextCursor'
        CONTENT = 'content'
        IS_ERROR = 'isError'
        NAME = 'name'
        INPUT_SCHEMA = 'inputSchema'
        DESCRIPTION = 'description'
        TYPE = 'type'
        # The member of a text item that holds its text, and its type.
        TEXT = 'text'
        private_constant :TOOLS, :NEXT_CURSOR, :CONTENT, :IS_ERROR, :NAME, :INPUT_SCHEMA, :DESCRIPTION, :TYPE, :TEXT
        # The tools on a page of tools/list, a Wire::Response, each schema as the server wrote it; nil when it cannot
        # be read.
        def self.tools(page)
          tools = page.result[TOOLS]
          return unless tools.instance_of?(Array)

          written = RawJson.elements(RawJson.member(page.result_text, TOOLS))
          written.zip(tools).map { |text, item| tool(item, text) or return nil }
        rescue JSON::ParserError
          # Text the reader cannot follow, which only a parser that accepts more than JSON lets through.
          nil
        end

        # The cursor of the page after this one; nil on the last page.
        def self.next_cursor(page)
          cursor = page.result[NEXT_CURSOR]
          cursor if cursor.instance_of?(String) && !cursor.empty?
        end

        # What a tools/call result says: its content, one item a line, with any item that is not text named by its
        # type, and whether it is an error; nil when it cannot be read.
        def self.call_result(result)
          content = result[CONTENT]
          return unless content.instance_of?(Array)

          text = content.map { content_text(it) or return nil }
          CallResult.new(text: text.join("\n").freeze, error: result[IS_ERROR] == true)
        end

        def self.tool(item, text)
          return unless item.instance_of?(Hash)

          name, input_schema, description = item.values_at(NAME, INPUT_SCHEMA, DESCRIPTION)
          return unless name.instance_of?(String) && input_schema.instance_of?(Hash)

          Tool.new(name:, description: description.to_s, input_schema: RawJson.member(text, INPUT_SCHEMA))
        end

        def self.content_text(item)
          return unless item.instance_of?(Hash)

          type, text = item.values_at(TYPE, TEXT)
          case type
          when TEXT then text if text.instance_of?(String)
          when String then "[#{type} content]"
          end
        end
        private_class_method :tool, :content_text
      end
      private_constant :Results
    end
  end
end
