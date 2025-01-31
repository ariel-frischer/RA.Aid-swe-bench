# Project Improvements TODO List

## Documentation & Code Quality
- [ ] Enhance comprehensive documentation and add clear docstrings across all modules
- [ ] Strengthen type hints and inline comments in critical files (esp. agent_runner.py)
- [ ] Update documentation in Makefile targets for clarity and consistency
- [ ] Add architecture diagrams and flow charts to README.md

## Configuration & Environment
- [ ] Implement proper .env file handling instead of relying on SHELL env vars
- [ ] Streamline configuration in config.py for better Python version support
- [ ] Document environment variable requirements more clearly
- [ ] Add validation for required environment variables

## Testing & Evaluation 
- [ ] Expand unit test coverage across core functionality
- [ ] Reorganize prediction files into dated run folders
- [ ] Fix post-evaluation processing issues
- [ ] Improve error logging for failed predictions
- [ ] Add integration tests for repository management
- [ ] Implement test result analysis in prompt generation

## Repository Management & Performance
- [ ] Enhance virtual environment activation robustness
- [ ] Optimize parallel processing and prevent runaway processes
- [ ] Improve git worktree management and caching
- [ ] Add monitoring for disk usage and cleanup old caches
- [ ] Implement better timeout handling for long-running processes

## Code Cleanup
- [ ] Remove or update deprecated functions (e.g., get_agent_config)
- [ ] Address intermittent RA.Aid runtime errors
- [ ] Standardize error handling across modules
- [ ] Implement proper logging levels and output formatting
- [ ] Add input validation and sanitization

## Security & Safety
- [ ] Review and document security implications of cowboy mode
- [ ] Add safeguards for dangerous shell commands
- [ ] Implement rate limiting for API calls
- [ ] Add checksums verification for downloaded dependencies
- [ ] Document security best practices for users

## Future Enhancements
- [ ] Support for additional LLM providers
- [ ] Improved cost tracking and reporting
- [ ] Better handling of repository dependencies
- [ ] Enhanced prompt engineering capabilities
- [ ] Support for custom evaluation metrics

## Known Issues
- Tool errors with syntax and string parsing
- Inconsistent behavior with different models
- Memory usage during parallel processing
- Rate limiting with certain API providers
- Virtual environment activation issues
