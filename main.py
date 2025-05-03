from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label

class Calculator(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        self.input1 = TextInput(hint_text="Enter first number", input_filter='float', multiline=False)
        self.input2 = TextInput(hint_text="Enter second number", input_filter='float', multiline=False)
        self.result = Label(text="Result: ")

        self.add_widget(self.input1)
        self.add_widget(self.input2)

        button_layout = BoxLayout(size_hint_y=0.3)

        for symbol in ['+', '-', '*', '/']:
            btn = Button(text=symbol)
            btn.bind(on_press=self.calculate)
            button_layout.add_widget(btn)

        self.add_widget(button_layout)
        self.add_widget(self.result)

    def calculate(self, instance):
        try:
            num1 = float(self.input1.text)
            num2 = float(self.input2.text)
            op = instance.text

            if op == '+':
                res = num1 + num2
            elif op == '-':
                res = num1 - num2
            elif op == '*':
                res = num1 * num2
            elif op == '/':
                res = num1 / num2 if num2 != 0 else "Cannot divide by zero"

            self.result.text = f"Result: {res}"
        except:
            self.result.text = "Invalid input"

class CalculatorApp(App):
    def build(self):
        return Calculator()

if __name__ == "__main__":
    CalculatorApp().run()