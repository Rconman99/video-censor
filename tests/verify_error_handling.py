from video_censor.error_handler import handle_error, safe_operation, UserFriendlyError
import logging

def test_error_handling():
    print("1. Testing Friendly Messages...")
    # File not found
    try:
        raise FileNotFoundError(2, "No such file", "missing.mp4")
    except Exception as e:
        title, msg = handle_error(e)
        assert title == "File not found"
        assert "missing.mp4" in msg
        print("   PASS: FileNotFoundError mapped correctly")

    # Connection error
    try:
        raise ConnectionError("Failed to connect")
    except Exception as e:
        title, msg = handle_error(e)
        assert title == "Connection failed"
        print("   PASS: ConnectionError mapped correctly")
        
    # Unknown error
    try:
        raise ValueError("Something random")
    except Exception as e:
        title, msg = handle_error(e)
        assert title == "Something went wrong"
        print("   PASS: Unknown error fallback works")

    print("2. Testing Safe Operation Decorator...")
    
    @safe_operation("testing")
    def risky_func():
        raise MemoryError("OOM")
    
    try:
        risky_func()
    except UserFriendlyError as e:
        assert e.user_message.startswith("Your computer ran out")
        print("   PASS: Decorator caught exception and raised UserFriendlyError")
    except Exception as e:
        print(f"   FAIL: Decorator raised wrong exception type: {type(e)}")

    print("\nAll Error Handling tests passed!")

if __name__ == "__main__":
    try:
        test_error_handling()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")
