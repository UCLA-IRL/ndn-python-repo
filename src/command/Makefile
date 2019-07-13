all: repo_command_parameter_pb2.py repo_command_response_pb2.py

repo_command_parameter_pb2.py: repo_command_parameter.proto
	/usr/local/bin/protoc --python_out=. repo_command_parameter.proto

repo_command_response_pb2.py: repo_command_response.proto
	/usr/local/bin/protoc --python_out=. repo_command_response.proto

clean:
	rm -f repo_command_parameter_pb2.py repo_command_response_pb2.py