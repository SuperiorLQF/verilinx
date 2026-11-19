#include "libavoid/libavoid.h"

#include <array>
#include <cstddef>
#include <memory>
#include <vector>

using Rect = std::array<double, 4>;

extern "C" {
struct VlxConnection {
    double sx, sy, tx, ty;
    unsigned source_direction, target_direction;
    std::size_t checkpoint_offset, checkpoint_count;
};
}

namespace {
struct Link {
    Avoid::ConnRef* ref = nullptr;
    std::array<double, 4> endpoints{};
    unsigned source_direction = 0;
    unsigned target_direction = 0;
    std::vector<Avoid::Point> checkpoints;
};

struct Scene {
    Scene(std::size_t shapes, std::size_t nets, double padding)
        : router(Avoid::OrthogonalRouting), boxes(shapes), geometry(shapes), links(nets) {
        router.setRoutingParameter(Avoid::shapeBufferDistance, padding);
        router.setRoutingParameter(Avoid::idealNudgingDistance, 12);
        router.setRoutingParameter(Avoid::segmentPenalty, 18);
        router.setRoutingOption(Avoid::nudgeSharedPathsWithCommonEndPoint, true);
    }

    void sync_shape(std::size_t index, const double* coordinates) {
        const Rect bounds = {coordinates[0], coordinates[1], coordinates[2], coordinates[3]};
        if (boxes[index] && geometry[index] == bounds)
            return;
        Avoid::Rectangle shape({bounds[0], bounds[1]}, {bounds[2], bounds[3]});
        if (boxes[index])
            router.moveShape(boxes[index], shape);
        else
            boxes[index] = new Avoid::ShapeRef(&router, shape);
        geometry[index] = bounds;
    }

    void sync_link(std::size_t index, const VlxConnection& input, const double* coordinates) {
        auto& link = links[index];
        const std::array<double, 4> endpoints = {input.sx, input.sy, input.tx, input.ty};
        const Avoid::ConnEnd source({input.sx, input.sy}, input.source_direction);
        const Avoid::ConnEnd target({input.tx, input.ty}, input.target_direction);
        if (!link.ref)
            link.ref = new Avoid::ConnRef(&router, source, target);
        else if (link.endpoints != endpoints || link.source_direction != input.source_direction
                 || link.target_direction != input.target_direction)
            link.ref->setEndpoints(source, target);
        link.endpoints = endpoints;
        link.source_direction = input.source_direction;
        link.target_direction = input.target_direction;

        std::vector<Avoid::Point> checkpoints;
        for (std::size_t i = 0; i < input.checkpoint_count; ++i) {
            const auto j = 2 * (input.checkpoint_offset + i);
            checkpoints.emplace_back(coordinates[j], coordinates[j + 1]);
        }
        if (link.checkpoints != checkpoints) {
            link.checkpoints = std::move(checkpoints);
            std::vector<Avoid::Checkpoint> constraints;
            for (const auto& point : link.checkpoints)
                constraints.emplace_back(point);
            link.ref->setRoutingCheckpoints(constraints);
            link.ref->setEndpoints(source, target);
        }
    }

    Avoid::Router router;
    std::vector<Avoid::ShapeRef*> boxes;
    std::vector<Rect> geometry;
    std::vector<Link> links;
};

struct Session {
    explicit Session(double padding) : padding(padding) {}
    double padding;
    std::unique_ptr<Scene> scene;
};
} // namespace

extern "C" {
void* vlx_avoid_new(double padding) {
    try {
        return new Session(padding);
    } catch (...) {
        return nullptr;
    }
}

void vlx_avoid_free(void* handle) {
    delete static_cast<Session*>(handle);
}

int vlx_avoid_route(void* handle, std::size_t shape_count, const double* shapes,
                    std::size_t net_count, const VlxConnection* nets, const double* checkpoints) {
    auto& session = *static_cast<Session*>(handle);
    try {
        if (!session.scene || session.scene->boxes.size() != shape_count
            || session.scene->links.size() != net_count) {
            session.scene = std::make_unique<Scene>(shape_count, net_count, session.padding);
        }
        auto& scene = *session.scene;
        for (std::size_t i = 0; i < shape_count; ++i)
            scene.sync_shape(i, shapes + 4 * i);
        for (std::size_t i = 0; i < net_count; ++i)
            scene.sync_link(i, nets[i], checkpoints);
        scene.router.processTransaction();
        return 1;
    } catch (...) {
        session.scene.reset();
        return 0;
    }
}

std::size_t vlx_avoid_path(void* handle, std::size_t net, double* coordinates, std::size_t capacity) {
    try {
        auto& scene = *static_cast<Session*>(handle)->scene;
        const auto& points = scene.links[net].ref->displayRoute().ps;
        if (coordinates && capacity >= points.size()) {
            for (std::size_t i = 0; i < points.size(); ++i) {
                coordinates[i * 2] = points[i].x;
                coordinates[i * 2 + 1] = points[i].y;
            }
        }
        return points.size();
    } catch (...) {
        return 0;
    }
}
}
