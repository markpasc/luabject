import village._luabject

state = village._luabject.new()
village._luabject.load_script(state, "function foo() prant() end")

print repr(state)
