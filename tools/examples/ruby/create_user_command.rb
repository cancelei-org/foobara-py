require "foobara"

# Creates a new user account with validation
class CreateUser < Foobara::Command
  inputs do
    name :string, :required, min_length: 1, max_length: 100
    email :email, :required
    age :integer, min: 0, max: 150
    tags :array, element_type: :string
    role :string, one_of: ["admin", "user", "guest"], default: "user"
    bio :string, max_length: 500
  end

  result :entity

  def execute
    # Validate email format
    validate_email_format

    # Check for duplicate
    check_duplicate_email

    # Create the user
    create_user_record

    user
  end

  attr_accessor :user

  def validate_email_format
    unless email.include?("@") && email.include?(".")
      add_input_error(
        key: :email,
        error_class: InvalidEmailFormat
      )
    end
  end

  def check_duplicate_email
    if User.exists?(email: email)
      add_runtime_error(
        key: :email,
        message: "Email already registered"
      )
    end
  end

  def create_user_record
    self.user = User.create!(
      name: name,
      email: email,
      age: age,
      tags: tags || [],
      role: role,
      bio: bio
    )
  end
end
