#include <givp/givp.hpp>
#include <iostream>
#include <vector>

int main() {
    auto objective = [](const std::vector<double>& solution) {
        double sum = 0;
        for (double x : solution) sum += x;
        return sum;
    };
    std::vector<std::pair<double, double>> bounds = {{0.0, 10.0}, {0.0, 10.0}};

    auto result = givp::givp(objective, bounds);
    std::cout << "Success: " << result.fun << std::endl;
    return 0;
}
