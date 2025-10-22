import com.sun.net.httpserver.*;
import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.stream.*;

public class AverageServer {

    public static void main(String[] args) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(8199), 0);
        server.createContext("/", exchange -> {
            if ("POST".equals(exchange.getRequestMethod())) {
                InputStream is = exchange.getRequestBody();
                String body = new String(is.readAllBytes(), StandardCharsets.UTF_8);
                is.close();

                // parse JSON manually
                String numbersPart = body.replaceAll("[^0-9,]", "");
                String[] nums = numbersPart.split(",");
                int sum = 0;
                for (String n : nums) {
                    sum += Integer.parseInt(n);
                }
                int avg = nums.length > 0 ? sum / nums.length : 0;

                String response = Integer.toString(avg);
                exchange.getResponseHeaders().set("Content-Type", "text/plain");
                exchange.sendResponseHeaders(200, response.length());
                OutputStream os = exchange.getResponseBody();
                os.write(response.getBytes());
                os.close();
            } else {
                exchange.sendResponseHeaders(405, -1); // Method Not Allowed
            }
        });

        server.setExecutor(null);
        server.start();
        System.out.println("Server running on port 8199...");
    }
}

