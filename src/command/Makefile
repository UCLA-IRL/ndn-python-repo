all: repo_command_parameter_pb2.py repo_command_response_pb2.py repo_storage_format_pb2.py

repo_command_parameter_pb2.py: repo_command_parameter.proto
	protoc --python_out=. repo_command_parameter.proto

repo_command_response_pb2.py: repo_command_response.proto
	protoc --python_out=. repo_command_response.proto

repo_storage_format_pb2.py: repo_storage_format.proto
	protoc --python_out=. repo_storage_format.proto

clean:
	rm -f *.py