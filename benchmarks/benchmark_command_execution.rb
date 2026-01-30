#!/usr/bin/env ruby
# frozen_string_literal: true

# Performance benchmarks for command execution in foobara-ruby.
#
# This is the Ruby equivalent of benchmark_command_execution.py
# Run with: ruby benchmarks/benchmark_command_execution.rb
#
# Requirements:
#   gem install foobara
#   gem install benchmark-ips

require 'foobara'
require 'benchmark/ips'
require 'json'
require 'fileutils'

# ==================== Test Commands ====================

# 1. Simple command (baseline)
module SimpleCommands
  foobara_domain!

  class AddCommand < Foobara::Command
    inputs do
      a :integer
      b :integer
    end

    result :integer

    def execute
      inputs[:a] + inputs[:b]
    end
  end
end

# 2. Command with validation
module ValidatedCommands
  foobara_domain!

  class ValidatedAddCommand < Foobara::Command
    inputs do
      a :integer, :required, one_of: (0..1000).to_a
      b :integer, :required, one_of: (0..1000).to_a
    end

    result :integer

    def execute
      inputs[:a] + inputs[:b]
    end
  end
end

# 3. Command with lifecycle callbacks
module CallbackCommands
  foobara_domain!

  class CommandWithCallbacks < Foobara::Command
    inputs do
      value :integer
    end

    result :integer

    attr_accessor :callback_count

    def initialize(*args)
      super
      @callback_count = 0
    end

    before_execute do
      @callback_count += 1
    end

    after_execute do
      @callback_count += 1
    end

    def execute
      inputs[:value] * 2
    end
  end
end

# 4. Nested subcommand execution
module SubcommandCommands
  foobara_domain!

  class MultiplyCommand < Foobara::Command
    inputs do
      x :integer
      y :integer
    end

    result :integer

    def execute
      inputs[:x] * inputs[:y]
    end
  end

  class CompositeCommand < Foobara::Command
    inputs do
      a :integer
      b :integer
      c :integer
    end

    result :integer

    def execute
      # (a + b) * c
      sum_result = run_subcommand!(SimpleCommands::AddCommand, a: inputs[:a], b: inputs[:b])
      product_result = run_subcommand!(MultiplyCommand, x: sum_result, y: inputs[:c])
      product_result
    end
  end
end

# 5. Complex validation command
module ComplexCommands
  foobara_domain!

  class ComplexCommand < Foobara::Command
    inputs do
      name :string, :required, max_length: 100
      email :string, :required
      age :integer, :required, one_of: (0..120).to_a
      tags :array, element_type: :string, max_size: 10, default: []
      metadata :associative_array, default: {}
    end

    result do
      id :integer
      name :string
      status :string
    end

    def execute
      { id: 1, name: inputs[:name], status: 'active' }
    end
  end
end

# ==================== Benchmark Utilities ====================

class BenchmarkRunner
  attr_reader :results

  def initialize
    @results = {}
  end

  def run_benchmark(name, warmup: 2, time: 5)
    puts "\n#{'=' * 60}"
    puts name
    puts '=' * 60

    result = {}

    Benchmark.ips do |x|
      x.config(warmup: warmup, time: time)
      x.report(name) do
        yield
      end

      x.save! "#{name}.json"
    end

    result
  end

  def benchmark_simple_command
    run_benchmark("1. Simple Command Execution") do
      SimpleCommands::AddCommand.run(a: 5, b: 3)
    end
  end

  def benchmark_command_with_validation
    puts "\n#{'=' * 60}"
    puts "2. Command with Validation Benchmark"
    puts '=' * 60

    Benchmark.ips do |x|
      x.config(warmup: 2, time: 5)

      x.report("AddCommand (no validation)") do
        SimpleCommands::AddCommand.run(a: 5, b: 3)
      end

      x.report("ValidatedAddCommand (with validators)") do
        ValidatedCommands::ValidatedAddCommand.run(a: 5, b: 3)
      end

      x.compare!
    end
  end

  def benchmark_lifecycle_callbacks
    puts "\n#{'=' * 60}"
    puts "3. Lifecycle Callbacks Benchmark"
    puts '=' * 60

    Benchmark.ips do |x|
      x.config(warmup: 2, time: 5)

      x.report("AddCommand (no callbacks)") do
        SimpleCommands::AddCommand.run(a: 5, b: 3)
      end

      x.report("CommandWithCallbacks (2 callbacks)") do
        CallbackCommands::CommandWithCallbacks.run(value: 10)
      end

      x.compare!
    end
  end

  def benchmark_subcommands
    puts "\n#{'=' * 60}"
    puts "4. Subcommand Execution Benchmark"
    puts '=' * 60

    Benchmark.ips do |x|
      x.config(warmup: 2, time: 5)

      x.report("Single command") do
        SubcommandCommands::MultiplyCommand.run(x: 8, y: 3)
      end

      x.report("Composite command (2 subcommands)") do
        SubcommandCommands::CompositeCommand.run(a: 5, b: 3, c: 2)
      end

      x.compare!
    end
  end

  def benchmark_complex_validation
    puts "\n#{'=' * 60}"
    puts "5. Complex Validation Benchmark"
    puts '=' * 60

    Benchmark.ips do |x|
      x.config(warmup: 2, time: 5)

      x.report("Simple (2 int inputs)") do
        SimpleCommands::AddCommand.run(a: 5, b: 3)
      end

      x.report("Complex (5 fields with validation)") do
        ComplexCommands::ComplexCommand.run(
          name: "John Doe",
          email: "john@example.com",
          age: 30,
          tags: ["user", "active"],
          metadata: { "source" => "api", "version" => "1.0" }
        )
      end

      x.compare!
    end
  end

  def save_results(filename = "benchmark_results_ruby.json")
    output_dir = File.join(File.dirname(__FILE__), "results")
    FileUtils.mkdir_p(output_dir)

    output_file = File.join(output_dir, filename)

    results_with_metadata = {
      framework: "foobara-ruby",
      language: "ruby",
      timestamp: Time.now.to_i,
      ruby_version: RUBY_VERSION,
      benchmarks: @results
    }

    File.write(output_file, JSON.pretty_generate(results_with_metadata))
    puts "\nResults saved to: #{output_file}"
  end

  def run_all
    puts "\n"
    puts '=' * 60
    puts "FOOBARA-RUBY COMMAND EXECUTION BENCHMARKS"
    puts '=' * 60
    puts "Ruby implementation benchmark suite"
    puts "Ruby version: #{RUBY_VERSION}"

    benchmark_simple_command
    benchmark_command_with_validation
    benchmark_lifecycle_callbacks
    benchmark_subcommands
    benchmark_complex_validation

    puts "\n#{'=' * 60}"
    puts "SUMMARY"
    puts '=' * 60
    puts "\nAll benchmarks complete!"
    puts "Note: Individual benchmark results are saved in JSON format"
    puts "Use the comparison tools to analyze Python vs Ruby performance"

    save_results
  end
end

# ==================== Main ====================

if __FILE__ == $PROGRAM_NAME
  runner = BenchmarkRunner.new
  runner.run_all
end
