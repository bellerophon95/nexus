from simhash import Simhash
import sys

text = "This is a test document for simhash."
sh = Simhash(text)
print(f"Text: {text}")
print(f"Simhash: {sh.value}")
print(f"Hex: {hex(sh.value)}")
