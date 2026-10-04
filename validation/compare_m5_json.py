import json
import os


folder = r"D:\Ravi\PES\Sem-4\Main_Project\PCB-QA\Code_flow\outputs\stack-chan"

original_file = os.path.join(folder, "m5-pantilt.json")
generated_file = os.path.join(
    folder,
    "m5-pantilt_generated_from_16.json"
)


with open(original_file, "r", encoding="utf-8") as f:
    original = json.load(f)

with open(generated_file, "r", encoding="utf-8") as f:
    generated = json.load(f)


print("========== JSON COMPARISON ==========")

print()
print("Original:", original_file)
print("Generated:", generated_file)

print()
print("========== TOP-LEVEL KEYS ==========")

print("Original:")
print(list(original.keys()))

print()
print("Generated:")
print(list(generated.keys()))

print()
print("========== COMPONENT COUNT ==========")

print("Original:", len(original["components"]))
print("Generated:", len(generated["components"]))

print()
print("========== NET COUNT ==========")

print("Original:", len(original["nets"]))
print("Generated:", len(generated["nets"]))


print()
print("========== COMPONENT KEY COMPARISON ==========")

original_components = set(original["components"].keys())
generated_components = set(generated["components"].keys())

print("Components only in original:")
print(sorted(original_components - generated_components))

print()
print("Components only in generated:")
print(sorted(generated_components - original_components))


print()
print("========== NET KEY COMPARISON ==========")

original_nets = set(original["nets"].keys())
generated_nets = set(generated["nets"].keys())

print("Nets only in original:")
print(sorted(original_nets - generated_nets))

print()
print("Nets only in generated:")
print(sorted(generated_nets - original_nets))


print()
print("========== EXACT COMPONENT COMPARISON ==========")

component_differences = []

for ref in sorted(original_components & generated_components):

    if original["components"][ref] != generated["components"][ref]:
        component_differences.append(ref)

print("Number of different components:", len(component_differences))

if component_differences:
    print("Different components:")
    print(component_differences)
else:
    print("All common components are exactly equal.")


print()
print("========== EXACT NET COMPARISON ==========")

net_differences = []

for net_name in sorted(original_nets & generated_nets):

    if original["nets"][net_name] != generated["nets"][net_name]:
        net_differences.append(net_name)

print("Number of different nets:", len(net_differences))

if net_differences:
    print("Different nets:")
    print(net_differences)
else:
    print("All common nets are exactly equal.")


print()
print("========== COMPLETE JSON COMPARISON ==========")

if original == generated:
    print("RESULT: EXACT MATCH")
else:
    print("RESULT: DIFFERENCES FOUND")

print()
print("========== TOP-LEVEL VALUE DIFFERENCES ==========")

for key in original:
    if original[key] != generated[key]:
        print()
        print("KEY:", key)
        print("Original:")
        print(original[key])
        print()
        print("Generated:")
        print(generated[key])
        