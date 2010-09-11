import village._luabject

state = village._luabject.new()
print "hi"
village._luabject.load_script(state, "function foo() prant() end")
print "bye"

print repr(state)
