# ToT Solver

## Installation

To install ToT Solver, follow these steps:

1. Clone the repository:

   ```sh
   git clone https://github.com/itechify/tot-solver.git
   ```

2. Navigate to the cloned repository directory:

   ```sh
   cd tot-solver
   ```

3. Create a virtual environment (optional but recommended):

   ```sh
   python -m venv venv
   ```

4. Activate the virtual environment:
   - On Windows:

     ```sh
     source venv\Scripts\activate
     ```

   - On macOS/Linux:

     ```sh
     source venv/bin/activate
     ```

5. Install the required Python packages:

   ```sh
   pip install -r requirements.txt
   ```

## Usage

To run ToT Solver, execute the following command from the root directory of the cloned repository:

```sh
python tot_solver.py
```

Upon starting, the application will prompt you to select the Hearthstone log file (`Zone.log`). Navigate to your Hearthstone log directory, select the file, and the application will begin monitoring card offerings in real-time.
