def handle_dfb_attribute_error(default_return=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            self = args[0]
            try:
                return func(*args, **kwargs)
            except AttributeError as e:
                self.update_textBox.emit(f"DFB is not yet connected: {e}")
                if default_return is not None:
                    return default_return
        return wrapper
    return decorator
